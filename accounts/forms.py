from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import username_validator

User = get_user_model()

PASSWORD_HELP = (
    "En az 8 karakter. Çok yaygın veya sadece rakamlardan oluşan parolalar kabul edilmez."
)


class RegisterForm(forms.Form):
    username = forms.CharField(
        label="Kullanıcı adı",
        max_length=20,
        validators=[username_validator],
        help_text="3-20 karakter: harf, rakam ve _ kullanabilirsin. Anketlerde bu ad görünür.",
        error_messages={"required": "Bir kullanıcı adı seçmelisin."},
        widget=forms.TextInput(
            attrs={"class": "field__input", "autocomplete": "username", "autocapitalize": "none", "autofocus": True}
        ),
    )
    email = forms.EmailField(
        label="E-posta",
        help_text="Giriş yapmak için kullanılır. Kimseye gösterilmez.",
        error_messages={
            "required": "E-posta adresini yazmalısın.",
            "invalid": "Geçerli bir e-posta adresi yaz.",
        },
        widget=forms.EmailInput(attrs={"class": "field__input", "autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Parola",
        help_text=PASSWORD_HELP,
        strip=False,
        error_messages={"required": "Bir parola belirlemelisin."},
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Parola (tekrar)",
        strip=False,
        error_messages={"required": "Parolayı tekrar yazmalısın."},
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu kullanıcı adı zaten alınmış.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Bu e-posta ile zaten bir hesap var.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Parolalar eşleşmiyor.")
        elif password1:
            candidate = User(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
            try:
                validate_password(password1, candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        return User.objects.create_user(
            email=self.cleaned_data["email"],
            username=self.cleaned_data["username"],
            password=self.cleaned_data["password1"],
        )


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "E-posta veya parola hatalı.",
        "inactive": "Bu hesap devre dışı.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"] = forms.EmailField(
            label="E-posta",
            error_messages={
                "required": "E-posta adresini yazmalısın.",
                "invalid": "Geçerli bir e-posta adresi yaz.",
            },
            widget=forms.EmailInput(
                attrs={"class": "field__input", "autocomplete": "email", "autofocus": True}
            ),
        )
        self.fields["password"].label = "Parola"
        self.fields["password"].error_messages["required"] = "Parolanı yazmalısın."
        self.fields["password"].widget.attrs.update(
            {"class": "field__input", "autocomplete": "current-password"}
        )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class AdminUserCreationForm(forms.ModelForm):
    """Used only by the Django admin 'add user' page."""

    password1 = forms.CharField(label="Parola", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Parola (tekrar)", strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "username")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Parolalar eşleşmiyor.")
        return p2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password2")
        if password:
            try:
                validate_password(password, self.instance)
            except ValidationError as exc:
                self.add_error("password2", exc)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
