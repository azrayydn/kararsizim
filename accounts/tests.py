from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

GOOD_PASSWORD = "Gizli-Parola-2026"


def make_user(username="ayse", email="ayse@example.com", password=GOOD_PASSWORD):
    return User.objects.create_user(email=email, username=username, password=password)


class RegisterTests(TestCase):
    def post(self, **overrides):
        data = {
            "username": "ayse",
            "email": "Ayse@Example.com",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("accounts:register"), data)

    def test_page_opens(self):
        self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 200)

    def test_register_creates_user_and_logs_in(self):
        response = self.post()
        self.assertRedirects(response, reverse("polls:home"))
        user = User.objects.get(username="ayse")
        self.assertEqual(user.email, "ayse@example.com")  # stored lowercase
        self.assertNotEqual(user.password, GOOD_PASSWORD)  # hashed
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_username_is_case_insensitive(self):
        make_user(username="Ayse", email="baska@example.com")
        response = self.post(username="aYSE")
        self.assertEqual(User.objects.count(), 1)
        self.assertContains(response, "Bu kullanıcı adı zaten alınmış.")

    def test_duplicate_email_is_case_insensitive(self):
        make_user(username="baska", email="ayse@example.com")
        response = self.post(email="AYSE@EXAMPLE.COM")
        self.assertEqual(User.objects.count(), 1)
        self.assertContains(response, "Bu e-posta ile zaten bir hesap var.")

    def test_invalid_usernames_rejected(self):
        for bad in ["ab", "a" * 21, "ayşe", "ayse kaya", "ayse!", "<b>x</b>"]:
            with self.subTest(username=bad):
                self.post(username=bad)
                self.assertEqual(User.objects.count(), 0)

    def test_password_rules(self):
        self.post(password1="Farkli-Parola-1", password2="Baska-Parola-2")
        self.assertEqual(User.objects.count(), 0)
        self.post(password1="12345678", password2="12345678")
        self.assertEqual(User.objects.count(), 0)
        self.post(password1="kısa1", password2="kısa1")
        self.assertEqual(User.objects.count(), 0)

    def test_next_is_followed_only_when_safe(self):
        url = reverse("accounts:register")
        data = {
            "username": "ayse", "email": "a@example.com",
            "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD,
        }
        response = self.client.post(url, {**data, "next": "/anket/yeni/"})
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)
        self.client.logout()
        User.objects.all().delete()
        response = self.client.post(url, {**data, "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("polls:home"))

    def test_logged_in_user_is_redirected_away(self):
        make_user()
        self.client.login(email="ayse@example.com", password=GOOD_PASSWORD)
        self.assertRedirects(self.client.get(reverse("accounts:register")), reverse("polls:home"))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.login_url = reverse("accounts:login")

    def test_login_with_email_case_insensitive(self):
        response = self.client.post(
            self.login_url, {"username": " AYSE@Example.com ", "password": GOOD_PASSWORD}
        )
        self.assertRedirects(response, reverse("polls:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_gives_generic_message(self):
        response = self.client.post(
            self.login_url, {"username": "ayse@example.com", "password": "yanlis"}
        )
        self.assertContains(response, "E-posta veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_gives_same_message(self):
        response = self.client.post(
            self.login_url, {"username": "yok@example.com", "password": GOOD_PASSWORD}
        )
        self.assertContains(response, "E-posta veya parola hatalı.")

    def test_username_cannot_be_used_to_log_in(self):
        response = self.client.post(self.login_url, {"username": "ayse", "password": GOOD_PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_login_next_redirect_safe_and_unsafe(self):
        creds = {"username": "ayse@example.com", "password": GOOD_PASSWORD}
        response = self.client.post(self.login_url, {**creds, "next": "/anket/yeni/"})
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)
        self.client.logout()
        response = self.client.post(self.login_url, {**creds, "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("polls:home"))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("polls:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_full_flow_register_logout_login(self):
        self.client.logout()
        self.client.post(reverse("accounts:register"), {
            "username": "mehmet", "email": "mehmet@example.com",
            "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD,
        })
        self.client.post(reverse("accounts:logout"))
        response = self.client.post(
            self.login_url, {"username": "mehmet@example.com", "password": GOOD_PASSWORD}
        )
        self.assertRedirects(response, reverse("polls:home"))


class PrivacyTests(TestCase):
    def test_email_never_appears_in_pages(self):
        user = make_user(email="gizli.adres@example.com")
        pages = [reverse("polls:home"), reverse("accounts:login"), reverse("accounts:register")]
        for logged_in in (False, True):
            if logged_in:
                self.client.force_login(user)
            for url in pages:
                response = self.client.get(url, follow=True)
                self.assertNotContains(response, "gizli.adres@example.com")
        self.assertContains(self.client.get(reverse("polls:home")), "@ayse")

    def test_topbar_links_depend_on_login_state(self):
        home = self.client.get(reverse("polls:home"))
        self.assertContains(home, reverse("accounts:register"))
        self.client.force_login(make_user())
        home = self.client.get(reverse("polls:home"))
        self.assertContains(home, "Çıkış")
        self.assertNotContains(home, reverse("accounts:register"))


class ManagerAndAdminTests(TestCase):
    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="Admin@Example.com", username="yonetici", password=GOOD_PASSWORD
        )
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertEqual(admin.email, "admin@example.com")

    def test_db_level_case_insensitive_uniqueness(self):
        from django.db import IntegrityError, transaction

        make_user(username="Ayse", email="ayse@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="AYSE", email="x@example.com")

    def test_admin_pages_work(self):
        admin = User.objects.create_superuser(
            email="admin@example.com", username="yonetici", password=GOOD_PASSWORD
        )
        self.client.force_login(admin)
        target = make_user()
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/accounts/user/{target.pk}/change/").status_code, 200)
        response = self.client.post("/admin/accounts/user/add/", {
            "email": "yeni@example.com", "username": "yeni",
            "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="yeni").exists())
