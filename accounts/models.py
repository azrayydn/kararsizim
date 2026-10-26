from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager

username_validator = RegexValidator(
    regex=r"\A[A-Za-z0-9_]{3,20}\Z",
    message=(
        "Kullanıcı adı 3-20 karakter olmalı ve sadece harf (a-z), "
        "rakam ve alt çizgi (_) içermelidir."
    ),
)


class User(AbstractUser):
    """Logs in with e-mail. `username` is the public nickname shown on polls."""

    first_name = None
    last_name = None

    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )
    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta ile zaten bir hesap var."},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        verbose_name = "kullanıcı"
        verbose_name_plural = "kullanıcılar"
        constraints = [
            models.UniqueConstraint(Lower("username"), name="unique_username_ci"),
            models.UniqueConstraint(Lower("email"), name="unique_email_ci"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.username:
            self.username = self.username.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
