from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, RegisterForm


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return ""


def register(request):
    if request.user.is_authenticated:
        return redirect("polls:home")

    next_url = _safe_next(request)
    form = RegisterForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            # Two people grabbing the same name/e-mail at the same moment.
            form.add_error(None, "Bu kullanıcı adı veya e-posta az önce başkası tarafından alındı. Başka bir tane dene.")
        else:
            login(request, user)
            messages.success(request, f"Hoş geldin @{user.username}!")
            return redirect(next_url or "polls:home")

    return render(request, "accounts/register.html", {"form": form, "next": next_url})


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
