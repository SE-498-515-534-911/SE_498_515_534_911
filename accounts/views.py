from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:home')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
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
