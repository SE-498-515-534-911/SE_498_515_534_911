from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import SELF_REGISTRATION_ROLES, Role
from audit import services as audit

from . import throttle
from .validators import validate_password_strength, validate_username_format

User = get_user_model()


class RegistrationForm(forms.ModelForm):
    username = forms.CharField(
        max_length=30, validators=[validate_username_format]
    )
    email = forms.EmailField()
    password = forms.CharField(
        widget=forms.PasswordInput, validators=[validate_password_strength]
    )
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    # Only STUDENT and DATA_SCIENTIST are offered. A ChoiceField also rejects any
    # other submitted value (such as ADMIN) on the server, even if the HTML form
    # is tampered with (MLE-F-002).
    role = forms.ChoiceField(
        choices=[(r.value, r.label) for r in SELF_REGISTRATION_ROLES],
        initial=Role.STUDENT,
    )

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this e-mail already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            # The signal gave the new user a Student profile; apply the chosen role.
            user.profile.role = self.cleaned_data['role']
            user.profile.save()
        return user


class ApiRegistrationForm(RegistrationForm):
    """Same rules as RegistrationForm for the JSON API (US-15, MLE-F-001).

    The API sends no password confirmation, so that field is dropped.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['confirm_password']


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Incorrect username or password.',
        'locked': 'Too many failed logins. Try again in 15 minutes.',
    }

    def clean(self):
        """Apply the login lockout (MLE-SR-007c) around Django's credential check."""
        username = self.cleaned_data.get('username')
        # Checked before the credentials, as in SAD 4.2.1.
        if username and throttle.is_locked(username):
            audit.record_login_failed(username, request=self.request, target='locked')
            raise forms.ValidationError(self.error_messages['locked'], code='locked')
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            if username:
                throttle.record_failure(username)
            raise
        throttle.clear_failures(username)
        return cleaned
