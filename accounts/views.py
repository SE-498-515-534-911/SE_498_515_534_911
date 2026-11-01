from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from audit import services as audit
from audit.models import Action

from .forms import LoginForm, RegistrationForm
from .permissions import admin_required


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:home')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            audit.record(Action.REGISTER, user=user, target=f'user:{user.pk}', request=request)
            messages.success(request, 'Account created. Please log in.')
            return redirect('accounts:login')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    """Logs out on POST only (Django default) and redirects to login."""


@login_required
def home(request):
    return render(request, 'accounts/home.html')


@admin_required  # Admin only (MLE-F-002, MLE-F-016)
def admin_dashboard(request):
    """The Admin panel (SAD 4.5.3). Its script loads users, datasets and the
    audit log from /api/admin/; the page only needs the list of audit events
    for the filter box."""
    return render(request, 'accounts/admin_dashboard.html', {'actions': Action.choices})

