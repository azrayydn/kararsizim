from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.LoginView.as_view(), name="login"),
    # LogoutView only accepts POST (a form with a CSRF token in the top bar).
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
]
