from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from .models import Option, Poll
from .templatetags.polls_extras import ago

User = get_user_model()


def make_user(username="ayse", email="ayse@example.com"):
    return User.objects.create_user(email=email, username=username, password="Gizli-Parola-2026")


def make_poll(author, question="Sinema mı restoran mı?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question)
    for index, text in enumerate(options):
        Option.objects.create(poll=poll, text=text, position=index)
    return poll


class CreatePollTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.url = reverse("polls:create")

    def post(self, question="Bugün ne yapsam?", options=("Sinema", "Restoran"), **extra):
        return self.client.post(self.url, {"question": question, "option": list(options), **extra})

    def test_anonymous_is_sent_to_login_and_comes_back(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")
        self.assertEqual(self.client.post(self.url, {"question": "x"}).status_code, 302)
        self.assertEqual(Poll.objects.count(), 0)

    def test_form_page_opens_for_member(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="option"', count=3)  # 2 rows + the JS template

    def test_create_poll_success(self):
        self.client.force_login(self.user)
        response = self.post(options=("Sinema", "Restoran", "Evde film"))
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("polls:detail", args=[poll.pk]))
        self.assertEqual(poll.author, self.user)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Restoran", "Evde film"])

    def test_blank_option_rows_are_ignored(self):
        self.client.force_login(self.user)
        self.post(options=("Sinema", "", "  ", "Restoran", ""))
        self.assertEqual([o.text for o in Poll.objects.get().options.all()], ["Sinema", "Restoran"])

    def test_option_count_limits(self):
        self.client.force_login(self.user)
        self.assertContains(self.post(options=("Tek",)), "En az 2 seçenek")
        self.assertContains(self.post(options=("Tek", "  ")), "En az 2 seçenek")
        self.assertContains(self.post(options=list("abcdef")), "En fazla 5 seçenek")
        self.assertEqual(Poll.objects.count(), 0)
        self.post(options=list("abcde"))
        self.assertEqual(Option.objects.count(), 5)

    def test_duplicate_options_rejected_case_insensitive(self):
        self.client.force_login(self.user)
        self.assertContains(self.post(options=("Sinema", " sinema ")), "Aynı seçeneği")
        self.assertEqual(Poll.objects.count(), 0)

    def test_length_limits(self):
        self.client.force_login(self.user)
        self.assertContains(self.post(options=("a" * 101, "b")), "en fazla 100 karakter")
        self.assertContains(self.post(question="q" * 201), "en fazla 200 karakter")
        self.assertContains(self.post(question="   "), "Sorunu yazmalısın.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_whitespace_is_collapsed(self):
        self.client.force_login(self.user)
        self.post(question="  Ne\n\n  yapsam?  ", options=("  iki   boşluk ", "b"))
        poll = Poll.objects.get()
        self.assertEqual(poll.question, "Ne yapsam?")
        self.assertEqual(poll.options.first().text, "iki boşluk")

    def test_entered_values_survive_a_validation_error(self):
        self.client.force_login(self.user)
        response = self.post(question="Sorum", options=("a", "b", "c", "c"))
        self.assertContains(response, 'value="a"')
        self.assertContains(response, 'value="c"', count=2)
        self.assertContains(response, "Sorum")

    def test_option_position_unique_per_poll(self):
        poll = make_poll(self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Option.objects.create(poll=poll, text="Başka", position=0)


class FeedAndDetailTests(TestCase):
    def setUp(self):
        self.user = make_user(email="gizli.adres@example.com")

    def test_anonymous_can_view_feed_and_detail(self):
        poll = make_poll(self.user)
        self.assertContains(self.client.get(reverse("polls:home")), "Sinema mı restoran mı?")
        detail = self.client.get(reverse("polls:detail", args=[poll.pk]))
        self.assertContains(detail, "Sinema")
        self.assertContains(detail, "@ayse")

    def test_email_never_shown_on_poll_pages(self):
        poll = make_poll(self.user)
        for url in (reverse("polls:home"), reverse("polls:detail", args=[poll.pk])):
            self.assertNotContains(self.client.get(url), "gizli.adres@example.com")

    def test_empty_state(self):
        self.assertContains(self.client.get(reverse("polls:home")), "Henüz kimse kararsız kalmamış")

    def test_newest_first(self):
        old = make_poll(self.user, question="Eski anket")
        new = make_poll(self.user, question="Yeni anket")
        Poll.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        content = self.client.get(reverse("polls:home")).content.decode()
        self.assertLess(content.index("Yeni anket"), content.index("Eski anket"))

    def test_pagination(self):
        for i in range(16):
            make_poll(self.user, question=f"Soru {i}")
        first = self.client.get(reverse("polls:home"))
        self.assertEqual(len(first.context["page_obj"]), 15)
        second = self.client.get(reverse("polls:home") + "?page=2")
        self.assertEqual(len(second.context["page_obj"]), 1)
        self.assertEqual(self.client.get(reverse("polls:home") + "?page=abc").status_code, 200)
        self.assertEqual(self.client.get(reverse("polls:home") + "?page=999").status_code, 200)

    def test_feed_does_not_run_a_query_per_poll(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(reverse("polls:home"))
            return len(queries)

        for i in range(3):
            make_poll(self.user, question=f"Soru {i}")
        few = count_queries()
        for i in range(10):
            make_poll(self.user, question=f"Daha fazla {i}")
        self.assertEqual(count_queries(), few)  # same number of queries with 13 polls as with 3

    def test_detail_404(self):
        self.assertEqual(self.client.get(reverse("polls:detail", args=[9999])).status_code, 404)

    def test_html_is_escaped(self):
        poll = make_poll(self.user, question="<script>alert(1)</script>", options=("<b>x</b>", "y"))
        for url in (reverse("polls:home"), reverse("polls:detail", args=[poll.pk])):
            html = self.client.get(url).content.decode()
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertNotIn("<b>x</b>", html)

    def test_plus_button_and_create_link_present(self):
        self.assertContains(self.client.get(reverse("polls:home")), 'class="fab"')

    def test_deleting_author_deletes_polls(self):
        make_poll(self.user)
        self.user.delete()
        self.assertEqual((Poll.objects.count(), Option.objects.count()), (0, 0))


class AgoFilterTests(TestCase):
    def test_labels(self):
        now = timezone.now()
        self.assertEqual(ago(now - timedelta(seconds=10)), "az önce")
        self.assertEqual(ago(now - timedelta(minutes=5)), "5 dakika önce")
        self.assertEqual(ago(now - timedelta(hours=3)), "3 saat önce")
        self.assertEqual(ago(now - timedelta(days=2)), "2 gün önce")
        self.assertRegex(ago(now - timedelta(days=30)), r"^\d{1,2} \w+ \d{4}$")


# ---------------------------------------------------------------- Faz 3: votes
from .models import Vote  # noqa: E402
from .views import percentages  # noqa: E402


class PercentageTests(TestCase):
    def test_always_adds_up_to_100(self):
        self.assertEqual(percentages([0, 0, 0]), [0, 0, 0])
        self.assertEqual(percentages([5]), [100])
        self.assertEqual(sum(percentages([1, 1, 1])), 100)
        self.assertEqual(percentages([1, 1, 1]), [34, 33, 33])
        self.assertEqual(percentages([3, 1]), [75, 25])
        for counts in ([7, 3, 3], [1, 2, 4, 8, 16], [13, 13, 13, 13, 13]):
            self.assertEqual(sum(percentages(counts)), 100)


class VoteTests(TestCase):
    def setUp(self):
        self.author = make_user()
        self.voter = make_user(username="mehmet", email="mehmet@example.com")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran", "Evde film"))
        self.cinema, self.restaurant, self.home_opt = list(self.poll.options.all())
        self.vote_url = reverse("polls:vote", args=[self.poll.pk])
        self.detail_url = reverse("polls:detail", args=[self.poll.pk])

    def test_guest_vote_goes_to_login_and_back_to_poll_page(self):
        response = self.client.post(self.vote_url, {"option": self.cinema.pk})
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={self.detail_url}", fetch_redirect_response=False
        )
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_requires_post(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.client.get(self.vote_url).status_code, 405)

    def test_member_can_vote_once(self):
        self.client.force_login(self.voter)
        response = self.client.post(self.vote_url, {"option": self.cinema.pk}, follow=True)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, "Oyun kaydedildi!")
        self.assertEqual(Vote.objects.get().option, self.cinema)

    def test_second_vote_is_rejected_even_for_another_option(self):
        self.client.force_login(self.voter)
        self.client.post(self.vote_url, {"option": self.cinema.pk})
        response = self.client.post(self.vote_url, {"option": self.restaurant.pk}, follow=True)
        self.assertContains(response, "zaten oy verdin")
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().option, self.cinema)

    def test_db_enforces_one_vote_per_user_per_poll(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.voter)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=self.restaurant, user=self.voter)

    def test_option_from_another_poll_or_garbage_is_rejected(self):
        other = make_poll(self.author, question="Başka anket", options=("x", "y"))
        foreign = other.options.first()
        self.client.force_login(self.voter)
        for bad in (foreign.pk, "abc", "", "-1", "9999", "1 OR 1=1"):
            response = self.client.post(self.vote_url, {"option": bad}, follow=True)
            self.assertContains(response, "Bir seçenek seçmelisin.")
        self.client.post(self.vote_url, {})
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_on_missing_poll_is_404(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.client.post(reverse("polls:vote", args=[9999]), {"option": 1}).status_code, 404)

    def test_author_may_vote_on_own_poll(self):
        self.client.force_login(self.author)
        self.client.post(self.vote_url, {"option": self.cinema.pk})
        self.assertEqual(Vote.objects.count(), 1)

    def test_guest_sees_results_but_no_vote_form(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.voter)
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "100%")
        self.assertContains(response, "2 oy")
        self.assertContains(response, "Oy vermek için giriş yapmalısın.")
        self.assertNotContains(response, 'name="option"')
        self.assertContains(response, f"?next={self.detail_url}")

    def test_member_who_has_not_voted_sees_form_and_results(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        self.client.force_login(self.voter)
        response = self.client.get(self.detail_url)
        self.assertContains(response, 'name="option"', count=3)
        self.assertContains(response, "Oyumu kullan")
        self.assertContains(response, "100%")  # results are visible to everyone

    def test_voter_sees_checkmark_and_no_form(self):
        Vote.objects.create(poll=self.poll, option=self.restaurant, user=self.voter)
        self.client.force_login(self.voter)
        response = self.client.get(self.detail_url)
        self.assertNotContains(response, 'name="option"')
        self.assertNotContains(response, "Oyumu kullan")
        self.assertContains(response, "Senin seçimin", count=1)
        self.assertContains(response, "Oyunu kullandın")
        self.assertContains(response, "result--mine", count=1)

    def test_winner_and_ties(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        response = self.client.get(self.detail_url)
        self.assertEqual([r["is_winner"] for r in response.context["rows"]], [True, False, False])
        Vote.objects.create(poll=self.poll, option=self.restaurant, user=self.voter)
        response = self.client.get(self.detail_url)
        self.assertEqual([r["is_winner"] for r in response.context["rows"]], [True, True, False])

    def test_no_votes_yet(self):
        response = self.client.get(self.detail_url)
        self.assertEqual([r["is_winner"] for r in response.context["rows"]], [False] * 3)
        self.assertEqual(response.context["total"], 0)
        self.assertContains(response, "Henüz oy yok")

    def test_percentages_shown_add_up(self):
        third = make_user(username="ali", email="ali@example.com")
        for option, user in ((self.cinema, self.author), (self.restaurant, self.voter), (self.home_opt, third)):
            Vote.objects.create(poll=self.poll, option=option, user=user)
        rows = self.client.get(self.detail_url).context["rows"]
        self.assertEqual(sum(r["pct"] for r in rows), 100)

    def test_feed_card_shows_total_votes_and_keeps_order(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.voter)
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        self.assertContains(self.client.get(reverse("polls:home")), "2 oy")

    def test_detail_query_count_does_not_grow_with_votes(self):
        self.client.force_login(self.voter)

        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(self.detail_url)
            return len(queries)

        before = count_queries()
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        self.assertEqual(count_queries(), before)

    def test_votes_removed_with_poll_and_with_user(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.voter)
        self.voter.delete()
        self.assertEqual(Vote.objects.count(), 0)
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        self.poll.delete()
        self.assertEqual(Vote.objects.count(), 0)

    def test_email_not_exposed_on_results(self):
        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.voter)
        self.assertNotContains(self.client.get(self.detail_url), "mehmet@example.com")
        self.assertNotContains(self.client.get(self.detail_url), "ayse@example.com")


# ------------------------------------------------- Faz 4: Anketlerim, silme, hata sayfaları
class MyPollsAndDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.other = make_user(username="mehmet", email="mehmet@example.com")
        self.poll = make_poll(self.owner, question="Benim anketim")
        self.others_poll = make_poll(self.other, question="Başkasının anketi")
        self.delete_url = reverse("polls:delete", args=[self.poll.pk])

    def test_my_polls_requires_login(self):
        response = self.client.get(reverse("polls:mine"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('polls:mine')}")

    def test_my_polls_lists_only_own_polls_with_delete_button(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("polls:mine"))
        self.assertContains(response, "Benim anketim")
        self.assertNotContains(response, "Başkasının anketi")
        self.assertContains(response, self.delete_url)
        self.assertContains(response, "data-confirm")

    def test_my_polls_empty_state(self):
        self.client.force_login(make_user(username="yeni", email="yeni@example.com"))
        self.assertContains(self.client.get(reverse("polls:mine")), "Henüz anket açmadın")

    def test_feed_has_no_delete_buttons(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse("polls:home")), "/sil/")

    def test_owner_can_delete_with_votes(self):
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), user=self.other)
        self.client.force_login(self.owner)
        response = self.client.post(self.delete_url, follow=True)
        self.assertRedirects(response, reverse("polls:mine"))
        self.assertContains(response, "Anketin silindi.")
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())
        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(Poll.objects.count(), 1)

    def test_other_member_cannot_delete(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.delete_url).status_code, 404)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_guest_cannot_delete(self):
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_delete_requires_post(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.delete_url).status_code, 405)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_delete_missing_poll_is_404(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("polls:delete", args=[9999])).status_code, 404)

    def test_detail_shows_delete_button_only_to_owner(self):
        url = reverse("polls:detail", args=[self.poll.pk])
        self.assertNotContains(self.client.get(url), "Anketi sil")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), "Anketi sil")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), "Anketi sil")

    def test_topbar_username_links_to_my_polls(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("polls:home")), f'href="{reverse("polls:mine")}"')


class ErrorPageTests(TestCase):
    def test_custom_404(self):
        response = self.client.get("/olmayan-sayfa/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Bu sayfa kararsız kalıp kaybolmuş", status_code=404)
        self.assertContains(response, "Ana sayfaya dön", status_code=404)

    def test_500_template_is_standalone(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")
        self.assertIn("Bir şeyler ters gitti", html)
        self.assertNotIn("{%", html)

    def test_csrf_failure_page_is_turkish(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:login"), {"username": "a@b.co", "password": "x"})
        self.assertContains(response, "Sayfanın süresi dolmuş", status_code=403)


# ------------------------------------------------------------- yan paneller
class SidePanelTests(TestCase):
    def setUp(self):
        self.a = make_user()
        self.b = make_user(username="mehmet", email="mehmet@example.com")
        self.c = make_user(username="ali", email="ali@example.com")

    def test_how_it_works_and_stats_are_rendered(self):
        poll = make_poll(self.a)
        Vote.objects.create(poll=poll, option=poll.options.first(), user=self.b)
        html = self.client.get(reverse("polls:home")).content.decode()
        self.assertIn("Nasıl çalışır?", html)
        self.assertIn("Popüler anketler", html)
        stats = self.client.get(reverse("polls:home"))
        self.assertContains(stats, '<dd>1</dd>', count=2)  # 1 poll, 1 vote
        self.assertContains(stats, '<dd>3</dd>')            # 3 members

    def test_popular_orders_by_votes_skips_empty_and_caps_at_five(self):
        quiet = make_poll(self.a, question="Sessiz anket")
        big = make_poll(self.a, question="Çok oy alan")
        small = make_poll(self.a, question="Az oy alan")
        Vote.objects.create(poll=big, option=big.options.first(), user=self.a)
        Vote.objects.create(poll=big, option=big.options.first(), user=self.b)
        Vote.objects.create(poll=small, option=small.options.first(), user=self.a)
        html = self.client.get(reverse("polls:home")).content.decode()
        side = html[html.index('aria-label="Popüler anketler"'):]
        self.assertLess(side.index("Çok oy alan"), side.index("Az oy alan"))
        self.assertNotIn("Sessiz anket", side)
        for i in range(7):
            poll = make_poll(self.a, question=f"Kalabalık {i}")
            Vote.objects.create(poll=poll, option=poll.options.first(), user=self.c)
        html = self.client.get(reverse("polls:home")).content.decode()
        side = html[html.index('aria-label="Popüler anketler"'):]
        self.assertEqual(side.count('class="popular__link"'), 5)

    def test_empty_popular_message(self):
        self.assertContains(self.client.get(reverse("polls:home")), "Henüz oy verilmiş anket yok")

    def test_panels_on_every_page_and_no_emails(self):
        make_poll(self.a)
        for url in (reverse("accounts:login"), reverse("polls:home"), "/yok/"):
            response = self.client.get(url)
            self.assertContains(response, "Nasıl çalışır?", status_code=response.status_code)
            self.assertNotContains(response, "ayse@example.com", status_code=response.status_code)

    def test_side_panels_do_not_add_queries_per_poll(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(reverse("accounts:login"))
            return len(queries)

        few = count_queries()
        for i in range(8):
            poll = make_poll(self.a, question=f"Soru {i}")
            Vote.objects.create(poll=poll, option=poll.options.first(), user=self.b)
        self.assertEqual(count_queries(), few)


class BrandingTests(TestCase):
    def test_logo_file_exists_and_is_used_in_page_and_favicon(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("img/logo.svg"))
        html = self.client.get(reverse("polls:home")).content.decode()
        self.assertIn('class="logo__mark"', html)
        self.assertIn('rel="icon"', html)
        self.assertNotIn("🤔", html)


# ------------------------------------------- tekrarlayan butonlar + özet kartı
from .insights import summarize  # noqa: E402


class SingleCreateEntryPointTests(TestCase):
    CREATE = 'href="/anket/yeni/"'

    def setUp(self):
        self.user = make_user()

    def test_exactly_one_create_link_for_guests_and_members(self):
        make_poll(self.user)
        pages = [reverse("polls:home"), reverse("polls:detail", args=[Poll.objects.get().pk])]
        for logged_in in (False, True):
            if logged_in:
                self.client.force_login(self.user)
            for url in pages:
                self.assertContains(self.client.get(url), self.CREATE, count=1)

    def test_empty_feed_and_empty_my_polls_have_no_extra_create_buttons(self):
        self.assertContains(self.client.get(reverse("polls:home")), self.CREATE, count=1)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("polls:mine")), self.CREATE, count=1)

    def test_fab_has_label_for_wide_screens(self):
        self.assertContains(self.client.get(reverse("polls:home")), "fab__label")


def _rows(counts, mine=None):
    class Opt:
        def __init__(self, text, position):
            self.text, self.position = text, position

    total = sum(counts)
    from .views import percentages

    pcts = percentages(counts)
    return [
        {"option": Opt(f"Seçenek {i}", i), "count": c, "pct": p, "is_mine": i == mine}
        for i, (c, p) in enumerate(zip(counts, pcts))
    ], total


class InsightTests(TestCase):
    def moods(self, counts, **kwargs):
        rows, total = _rows(counts, mine=kwargs.pop("mine", None))
        result = summarize(rows, total, has_voted=kwargs.pop("has_voted", False))
        return result["mood"] if result else None

    def test_no_votes_no_card(self):
        rows, total = _rows([0, 0])
        self.assertIsNone(summarize(rows, total, has_voted=False))

    def test_each_mood(self):
        self.assertEqual(self.moods([1, 1]), "Isınıyoruz")
        self.assertEqual(self.moods([5, 0]), "Oybirliği")
        self.assertEqual(self.moods([4, 4]), "Tam beraberlik")
        self.assertEqual(self.moods([3, 3, 3]), "Tam beraberlik")
        self.assertEqual(self.moods([10, 9]), "Kıran kırana")
        self.assertEqual(self.moods([14, 6]), "Net karar")
        self.assertEqual(self.moods([23, 17]), "Önde ama kesin değil")
        self.assertEqual(self.moods([18, 4]), "Net karar")
        self.assertEqual(self.moods([5, 5, 4, 4, 3]), "Tam beraberlik")
        self.assertEqual(self.moods([6, 5, 5, 4, 4]), "Fikirler dağınık")

    def test_close_race_uses_vote_difference_when_tiny(self):
        rows, total = _rows([50, 49])
        self.assertIn("sadece 1 oy fark var", summarize(rows, total, False)["text"])
        rows, total = _rows([120, 100])  # 9 points apart, but 20 votes: show the percentage instead
        text = summarize(rows, total, False)["text"]
        self.assertIn("sadece %9 fark var", text)
        self.assertNotIn("oy fark var", text)

    def test_personal_line(self):
        rows, total = _rows([6, 2], mine=0)
        self.assertIn("çoğunluğun yanındasın", summarize(rows, total, has_voted=True)["personal"])
        rows, total = _rows([6, 2], mine=1)
        self.assertIn("farklı düşünenlerdensin", summarize(rows, total, has_voted=True)["personal"])
        self.assertEqual(summarize(rows, total, has_voted=False)["personal"], "")
        rows, total = _rows([1, 1], mine=1)
        self.assertEqual(summarize(rows, total, has_voted=True)["personal"], "")  # too early to say

    def test_long_option_names_are_shortened(self):
        rows, total = _rows([8, 1])
        rows[0]["option"].text = "çok " * 40
        text = summarize(rows, total, False)["text"]
        self.assertIn("…", text)
        self.assertLess(len(text), 200)

    def test_all_texts_are_non_empty_and_sums_make_sense(self):
        import itertools

        for counts in itertools.product(range(0, 6), repeat=3):
            rows, total = _rows(list(counts))
            result = summarize(rows, total, False)
            if total == 0:
                self.assertIsNone(result)
            else:
                self.assertTrue(result["text"] and result["mood"])
                self.assertEqual(result["basis"], f"{total} oya göre")


class InsightCardPageTests(TestCase):
    def setUp(self):
        self.author = make_user()
        self.voter = make_user(username="mehmet", email="mehmet@example.com")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran"))
        self.cinema, self.restaurant = list(self.poll.options.all())
        self.url = reverse("polls:detail", args=[self.poll.pk])

    def test_no_card_without_votes(self):
        self.assertNotContains(self.client.get(self.url), "insight__text")

    def test_card_shows_for_guest_member_and_voter(self):
        users = [make_user(username=f"u{i}", email=f"u{i}@example.com") for i in range(4)]
        for u in users:
            Vote.objects.create(poll=self.poll, option=self.cinema, user=u)
        self.assertContains(self.client.get(self.url), "insight__text")  # guest
        self.client.force_login(self.voter)
        self.assertContains(self.client.get(self.url), "insight__text")  # member who can still vote
        self.client.post(reverse("polls:vote", args=[self.poll.pk]), {"option": self.cinema.pk})
        response = self.client.get(self.url)
        self.assertContains(response, "insight__personal")
        self.assertContains(response, "5 oya göre")

    def test_option_text_is_escaped_in_card(self):
        Option.objects.filter(pk=self.cinema.pk).update(text="<script>alert(1)</script>")
        users = [make_user(username=f"u{i}", email=f"u{i}@example.com") for i in range(3)]
        for u in users:
            Vote.objects.create(poll=self.poll, option=self.cinema, user=u)
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_card_needs_no_extra_queries(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(self.url)
            return len(queries)

        Vote.objects.create(poll=self.poll, option=self.cinema, user=self.author)
        with_votes = count_queries()
        for i in range(5):
            u = make_user(username=f"x{i}", email=f"x{i}@example.com")
            Vote.objects.create(poll=self.poll, option=self.restaurant, user=u)
        self.assertEqual(count_queries(), with_votes)


# ================================================== Acil Karar + rozetler
from .badges import BADGES, MIN_VOTES, badge_for, badges_for_users, profile_for, settle_due_polls  # noqa: E402
from .models import URGENT_MINUTES  # noqa: E402


def make_urgent(author, minutes=5, question="Acil mi?", options=("A", "B")):
    poll = make_poll(author, question=question, options=options)
    Poll.objects.filter(pk=poll.pk).update(closes_at=timezone.now() + timedelta(minutes=minutes))
    poll.refresh_from_db()
    return poll


def close(poll):
    Poll.objects.filter(pk=poll.pk).update(closes_at=timezone.now() - timedelta(seconds=1))
    poll.refresh_from_db()


def voters(n):
    result = []
    for i in range(n):
        user = User.objects.filter(username=f"v{i}").first() or make_user(
            username=f"v{i}", email=f"v{i}@example.com"
        )
        result.append(user)
    return result


def closed_poll(author, picks, question="Kapalı acil", options=("A", "B")):
    """Closed Acil Karar where voter i picked option picks[i]."""
    poll = make_urgent(author, question=question, options=options)
    opts = list(poll.options.all())
    for user, pick in zip(voters(len(picks)), picks):
        Vote.objects.create(poll=poll, option=opts[pick], user=user)
    close(poll)
    return poll


class UrgentCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("polls:create")

    def test_urgent_checkbox_sets_deadline(self):
        before = timezone.now()
        response = self.client.post(
            self.url, {"question": "Acil mi?", "option": ["A", "B"], "urgent": "on"}, follow=True
        )
        poll = Poll.objects.get()
        self.assertTrue(poll.is_urgent)
        self.assertAlmostEqual(
            (poll.closes_at - before).total_seconds(), URGENT_MINUTES * 60, delta=5
        )
        self.assertContains(response, "Acil Karar başladı")
        self.assertContains(response, "data-countdown")

    def test_normal_poll_has_no_deadline(self):
        self.client.post(self.url, {"question": "Acil değil", "option": ["A", "B"]})
        poll = Poll.objects.get()
        self.assertFalse(poll.is_urgent)
        self.assertFalse(poll.is_closed)

    def test_form_shows_the_checkbox(self):
        self.assertContains(self.client.get(self.url), "Acil Karar yap")


class UrgentVotingTests(TestCase):
    def setUp(self):
        self.author = make_user()
        self.me = make_user(username="mehmet", email="mehmet@example.com")
        self.poll = make_urgent(self.author)
        self.a, self.b = list(self.poll.options.all())
        self.url = reverse("polls:detail", args=[self.poll.pk])
        self.vote_url = reverse("polls:vote", args=[self.poll.pk])
        for user in voters(4):  # 3 for A, 1 for B, hidden from everyone
            Vote.objects.create(poll=self.poll, option=self.a if user.username != "v3" else self.b, user=user)

    def assertBlind(self, response):
        for leak in ("result__pct", "result__count", "--pct", "insight__text", "result--winner"):
            self.assertNotContains(response, leak)

    def test_results_are_hidden_for_everybody_while_open(self):
        self.assertBlind(self.client.get(self.url))  # guest
        self.client.force_login(self.me)
        self.assertBlind(self.client.get(self.url))  # member who has not voted
        self.client.post(self.vote_url, {"option": self.a.pk})
        self.assertBlind(self.client.get(self.url))  # member who voted
        self.client.force_login(self.author)
        self.assertBlind(self.client.get(self.url))  # the author

    def test_only_the_voter_count_is_visible_and_a_timer_runs(self):
        response = self.client.get(self.url)
        self.assertContains(response, "4 kişi oy verdi")
        self.assertContains(response, "data-countdown")
        self.assertContains(response, 'role="timer"')
        left = int(response.content.decode().split('data-seconds-left="')[1].split('"')[0])
        self.assertTrue(0 < left <= URGENT_MINUTES * 60)

    def test_can_vote_while_open(self):
        self.client.force_login(self.me)
        response = self.client.post(self.vote_url, {"option": self.b.pk}, follow=True)
        self.assertContains(response, "Sonuç süre dolunca açıklanacak")
        self.assertEqual(Vote.objects.filter(user=self.me).get().option, self.b)
        self.assertContains(response, "option-item--mine")  # own choice is marked, nothing else
        self.assertContains(response, "5 kişi oy verdi")

    def test_vote_form_is_blind_but_complete(self):
        self.client.force_login(self.me)
        response = self.client.get(self.url)
        self.assertContains(response, 'name="option"', count=2)
        self.assertContains(response, "result--blind", count=2)
        self.assertContains(response, "Sonuçlar süre dolunca açılır")

    def test_cannot_vote_after_the_deadline(self):
        close(self.poll)
        self.client.force_login(self.me)
        response = self.client.post(self.vote_url, {"option": self.a.pk}, follow=True)
        self.assertContains(response, "süresi doldu")
        self.assertFalse(Vote.objects.filter(user=self.me).exists())

    def test_closed_poll_reveals_locked_results(self):
        close(self.poll)
        self.client.force_login(self.me)
        response = self.client.get(self.url)
        self.assertContains(response, "Oylama kapandı, sonuç kilitlendi")
        self.assertContains(response, "75%")
        self.assertContains(response, "result--winner", count=1)
        self.assertContains(response, "Süre doldu, oylama kapandı.")  # I did not vote
        self.assertNotContains(response, 'name="option"')
        self.assertNotContains(response, "data-countdown")
        self.assertContains(response, "Süre doldu! ")  # summary card says the vote is over
        self.assertContains(response, "4 oyla kapandı")

    def test_closed_results_visible_to_guests_too(self):
        close(self.poll)
        response = self.client.get(self.url)
        self.assertContains(response, "75%")
        self.assertContains(response, "Süre doldu, oylama kapandı.")
        self.assertNotContains(response, "Oy vermek için giriş yapmalısın")  # voting is over, no point

    def test_feed_chips(self):
        make_poll(self.author, question="Sıradan anket")
        closed = closed_poll(self.author, [0, 0, 0], question="Bitti")
        response = self.client.get(reverse("polls:home"))
        html = response.content.decode()
        self.assertEqual(html.count("chip--urgent"), 1)
        self.assertEqual(html.count("chip--closed"), 1)
        self.assertContains(response, "data-countdown", count=1)

    def test_feed_cards_never_show_standings(self):
        html = self.client.get(reverse("polls:home")).content.decode()
        self.assertNotIn("result__pct", html)
        self.assertNotIn("75%", html)

    def test_normal_polls_are_unchanged(self):
        normal = make_poll(self.author, question="Normal")
        Vote.objects.create(poll=normal, option=normal.options.first(), user=self.me)
        response = self.client.get(reverse("polls:detail", args=[normal.pk]))
        self.assertContains(response, "100%")
        self.assertNotContains(response, "data-countdown")
        self.assertNotContains(response, "urgent-bar")

    def test_countdown_script_is_loaded(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("js/countdown.js"))
        self.assertContains(self.client.get(self.url), "js/countdown.js")


class SettlementTests(TestCase):
    def setUp(self):
        self.author = make_user()

    def test_clear_winner_is_recorded(self):
        poll = closed_poll(self.author, [0, 0, 0, 1, 1])
        settle_due_polls()
        poll.refresh_from_db()
        self.assertEqual(poll.winner.text, "A")
        self.assertIsNotNone(poll.settled_at)

    def test_tie_or_too_few_votes_have_no_winner(self):
        tie = closed_poll(self.author, [0, 0, 1, 1], question="Beraber")
        few = closed_poll(self.author, [0, 0, 0], question="Az oy")
        self.assertLess(3, MIN_VOTES)
        settle_due_polls()
        for poll in (tie, few):
            poll.refresh_from_db()
            self.assertIsNone(poll.winner)
            self.assertIsNotNone(poll.settled_at)

    def test_open_and_normal_polls_are_not_settled(self):
        open_poll = make_urgent(self.author, question="Açık")
        normal = make_poll(self.author, question="Normal")
        settle_due_polls()
        for poll in (open_poll, normal):
            poll.refresh_from_db()
            self.assertIsNone(poll.settled_at)

    def test_settling_is_idempotent(self):
        poll = closed_poll(self.author, [0, 0, 0, 1, 1])
        settle_due_polls()
        poll.refresh_from_db()
        first = poll.settled_at
        settle_due_polls()
        poll.refresh_from_db()
        self.assertEqual(poll.settled_at, first)


class BadgeTierTests(TestCase):
    def test_tiers(self):
        cases = {
            (2, 2): None,
            (3, 0): "cirak",
            (8, 4): "cirak",
            (8, 5): "verici",
            (20, 12): "verici",
            (20, 13): "master",
            (40, 29): "master",
            (40, 30): "guru",
        }
        for (total, hits), expected in cases.items():
            badge = badge_for(total, hits)
            self.assertEqual(badge.key if badge else None, expected, (total, hits))

    def test_tiers_are_ordered_highest_first(self):
        self.assertEqual([b.key for b in BADGES], ["guru", "master", "verici", "cirak"])


class BadgeFlowTests(TestCase):
    def setUp(self):
        self.asker = make_user(username="soran", email="soran@example.com")

    def three_settled_polls(self):
        # voter v0 always picks the winning option A
        for i in range(3):
            closed_poll(self.asker, [0, 0, 0, 1, 1], question=f"Acil {i}")

    def test_hits_earn_the_first_badge(self):
        self.three_settled_polls()
        v0 = User.objects.get(username="v0")
        badges = badges_for_users({v0.pk, User.objects.get(username="v3").pk})
        self.assertEqual(badges[v0.pk].key, "cirak")
        self.assertEqual(badge_for(*[3, 0]).key, "cirak")  # v3 always lost but still participates
        self.assertIn(User.objects.get(username="v3").pk, badges)

    def test_own_votes_and_non_urgent_polls_do_not_count(self):
        poll = make_urgent(self.asker, question="Kendi anketim")
        for user, pick in zip(voters(5), [0, 0, 0, 0, 0]):
            Vote.objects.create(poll=poll, option=poll.options.first(), user=user)
        Vote.objects.create(poll=poll, option=poll.options.first(), user=self.asker)
        close(poll)
        normal = make_poll(self.asker, question="Sıradan")
        Vote.objects.create(poll=normal, option=normal.options.first(), user=voters(1)[0])
        self.assertNotIn(self.asker.pk, badges_for_users({self.asker.pk}))  # voted on own poll only
        self.assertEqual(profile_for(voters(1)[0])["total"], 1)  # only the urgent poll counted

    def test_polls_without_winner_do_not_count(self):
        closed_poll(self.asker, [0, 0, 1, 1], question="Beraber")
        closed_poll(self.asker, [0, 0, 0], question="Az")
        self.assertEqual(badges_for_users({u.pk for u in voters(4)}), {})

    def test_badge_is_shown_next_to_the_name(self):
        self.three_settled_polls()
        v0 = User.objects.get(username="v0")
        mine = make_poll(v0, question="Rozetli kişinin anketi")
        feed = self.client.get(reverse("polls:home"))
        self.assertContains(feed, "🐣")
        detail = self.client.get(reverse("polls:detail", args=[mine.pk]))
        self.assertContains(detail, "Karar Çırağı")
        # the asker did not vote on anything, so no badge appears next to the asker
        self.assertNotContains(self.client.get(reverse("polls:detail", args=[Poll.objects.filter(author=self.asker).first().pk])), "badge--chip")

    def test_my_polls_shows_badge_card(self):
        self.client.force_login(self.asker)
        response = self.client.get(reverse("polls:mine"))
        self.assertContains(response, "Henüz rozetin yok")
        self.assertContains(response, "Karar Çırağı")  # next tier hint
        self.three_settled_polls()
        self.client.force_login(User.objects.get(username="v0"))
        response = self.client.get(reverse("polls:mine"))
        self.assertContains(response, "3 Acil Karar'dan 3 tanesinde")
        self.assertContains(response, "Karar Çırağı")
        self.assertContains(response, "Sıradaki: <strong>🎯 Karar Verici</strong>")
        # the card exists twice in the HTML: compact summary (narrow screens) and side panel (wide)
        self.assertContains(response, "badge-tier--now", count=2)

    def test_profile_next_tier_logic(self):
        profile = profile_for(self.asker)
        self.assertEqual((profile["total"], profile["current"]), (0, None))
        self.assertEqual(profile["next"].key, "cirak")

    def test_feed_query_count_stays_constant_with_badges(self):
        self.three_settled_polls()
        self.client.get(reverse("polls:home"))  # warm-up: the first visit settles the newly closed polls

        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(reverse("polls:home"))
            return len(queries)

        for u in voters(3):
            make_poll(u, question=f"A {u.pk}")
        few = count_queries()
        for u in voters(5):
            for i in range(3):
                make_poll(u, question=f"B {u.pk} {i}")
        self.assertEqual(count_queries(), few)

    def test_no_individual_votes_or_stats_leak_on_other_pages(self):
        self.three_settled_polls()
        poll = make_poll(User.objects.get(username="v0"), question="Rozetli")
        html = self.client.get(reverse("polls:detail", args=[poll.pk])).content.decode()
        self.assertNotIn("uyum", html)
        self.assertNotIn("tanesinde", html)


# ================================================================ fotoğraflar
import io  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from PIL import Image  # noqa: E402

from .images import MAX_UPLOAD_BYTES, process_upload  # noqa: E402
from .models import PollImage  # noqa: E402


def image_bytes(fmt="JPEG", size=(300, 200), color=(200, 60, 60), mode="RGB", **save_kwargs):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()


def upload(data, name="foto.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


class ProcessUploadTests(TestCase):
    def open(self, data):
        return Image.open(io.BytesIO(data))

    def test_jpeg_png_and_webp_become_webp(self):
        for fmt, name in (("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")):
            with self.subTest(fmt=fmt):
                result = process_upload(upload(image_bytes(fmt), name))
                self.assertEqual(self.open(result).format, "WEBP")

    def test_large_images_are_shrunk(self):
        result = process_upload(upload(image_bytes("JPEG", size=(3000, 2000))))
        self.assertLessEqual(max(self.open(result).size), 1200)

    def test_transparent_png_gets_white_background(self):
        data = image_bytes("PNG", size=(40, 40), color=(0, 0, 0, 0), mode="RGBA")
        result = self.open(process_upload(upload(data, "a.png", "image/png"))).convert("RGB")
        r, g, b = result.getpixel((20, 20))
        self.assertTrue(r > 240 and g > 240 and b > 240)

    def test_exif_location_is_removed_and_rotation_applied(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90°: a 60x30 picture should come out 30x60
        exif[0x8825] = {1: "N", 2: (41.0, 0.0, 0.0), 3: "E", 4: (29.0, 0.0, 0.0)}  # GPS info
        data = image_bytes("JPEG", size=(60, 30), exif=exif.tobytes())
        self.assertIn(0x8825, self.open(data).getexif())  # the test file really has a location
        result = self.open(process_upload(upload(data)))
        self.assertEqual(result.size, (30, 60))
        self.assertEqual(dict(result.getexif()), {})
        self.assertNotIn(b"Exif", process_upload(upload(data)))

    def test_not_an_image_is_rejected(self):
        for payload, name in ((b"merhaba, ben bir metin dosyasiyim", "a.jpg"), (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "a.svg"), (b"", "a.png")):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                process_upload(upload(payload, name))

    def test_gif_and_other_formats_are_rejected(self):
        with self.assertRaises(ValidationError):
            process_upload(upload(image_bytes("GIF"), "a.gif", "image/gif"))
        with self.assertRaises(ValidationError):
            process_upload(upload(image_bytes("BMP"), "a.bmp", "image/bmp"))

    def test_too_many_bytes_rejected(self):
        with self.assertRaises(ValidationError):
            process_upload(upload(b"0" * (MAX_UPLOAD_BYTES + 1)))

    def test_too_many_pixels_rejected(self):
        data = image_bytes("PNG", size=(7000, 7000), mode="1", color=0)  # tiny file, huge picture
        self.assertLess(len(data), MAX_UPLOAD_BYTES)
        with self.assertRaises(ValidationError):
            process_upload(upload(data, "a.png", "image/png"))

    def test_truncated_image_is_rejected(self):
        data = image_bytes("PNG", size=(500, 500))
        with self.assertRaises(ValidationError):
            process_upload(upload(data[: len(data) // 2], "a.png", "image/png"))

    def test_result_stays_small(self):
        noisy = Image.effect_noise((1600, 1200), 80).convert("RGB")
        buffer = io.BytesIO()
        noisy.save(buffer, format="JPEG", quality=95)
        self.assertLess(len(process_upload(upload(buffer.getvalue()))), 520 * 1024)


from django.core.exceptions import ValidationError  # noqa: E402


class PhotoPollTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("polls:create")

    def post(self, photo=None, **extra):
        data = {"question": "Hangisi?", "option": ["A", "B"], **extra}
        if photo is not None:
            data["image"] = photo
        return self.client.post(self.url, data)

    def test_create_poll_with_photo(self):
        response = self.post(upload(image_bytes("JPEG", size=(1600, 900))))
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("polls:detail", args=[poll.pk]))
        self.assertTrue(poll.has_image)
        stored = PollImage.objects.get(poll=poll)
        self.assertEqual(Image.open(io.BytesIO(bytes(stored.data))).format, "WEBP")

    def test_photo_is_optional(self):
        self.post()
        poll = Poll.objects.get()
        self.assertFalse(poll.has_image)
        self.assertEqual(PollImage.objects.count(), 0)

    def test_bad_file_blocks_the_whole_poll_with_a_message(self):
        response = self.post(upload(b"bu bir fotograf degil", "kotu.jpg"))
        self.assertContains(response, "Bu dosya geçerli bir fotoğraf değil.")
        self.assertContains(response, "fotoğrafı yeniden seçmen gerekiyor")
        self.assertEqual(Poll.objects.count(), 0)

    def test_form_page_is_multipart_and_offers_the_field(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'type="file"')
        self.assertContains(response, "data-photo-preview")

    def test_guest_cannot_upload(self):
        self.client.logout()
        response = self.post(upload(image_bytes()))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Poll.objects.count(), 0)

    def test_photo_url_serves_webp_with_short_cache(self):
        self.post(upload(image_bytes()))
        poll = Poll.objects.get()
        self.client.logout()  # polls are public
        response = self.client.get(reverse("polls:photo", args=[poll.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("s-maxage=3600", response["Cache-Control"])
        self.assertEqual(Image.open(io.BytesIO(response.content)).format, "WEBP")

    def test_photo_404_without_image_or_poll(self):
        poll = make_poll(self.user)
        self.assertEqual(self.client.get(reverse("polls:photo", args=[poll.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("polls:photo", args=[9999])).status_code, 404)

    def test_photo_shown_in_feed_and_detail_only_when_present(self):
        self.post(upload(image_bytes()))
        plain = make_poll(self.user, question="Fotoğrafsız")
        photo_url = reverse("polls:photo", args=[Poll.objects.exclude(pk=plain.pk).get().pk])
        feed = self.client.get(reverse("polls:home"))
        self.assertContains(feed, 'class="poll-photo"', count=1)
        self.assertContains(feed, 'loading="lazy"')
        self.assertContains(feed, photo_url)
        detail = self.client.get(reverse("polls:detail", args=[Poll.objects.exclude(pk=plain.pk).get().pk]))
        self.assertContains(detail, "poll-photo")
        self.assertNotContains(self.client.get(reverse("polls:detail", args=[plain.pk])), "poll-photo")

    def test_deleting_poll_deletes_photo_and_url_dies(self):
        self.post(upload(image_bytes()))
        poll = Poll.objects.get()
        self.client.post(reverse("polls:delete", args=[poll.pk]))
        self.assertEqual(PollImage.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("polls:photo", args=[poll.pk])).status_code, 404)

    def test_feed_queries_do_not_grow_with_photos_and_never_load_image_bytes(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(reverse("polls:home"))
            return queries

        for i in range(2):
            self.post(upload(image_bytes()))
        few = len(count_queries())
        for i in range(8):
            self.post(upload(image_bytes()))
        queries = count_queries()
        self.assertEqual(len(queries), few)
        self.assertFalse(any("polls_pollimage" in q["sql"] and '"data"' in q["sql"] for q in queries))

    def test_photo_text_in_alt_is_escaped(self):
        self.post(upload(image_bytes()), question='"><script>alert(1)</script>')
        html = self.client.get(reverse("polls:home")).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_admin_can_remove_a_photo(self):
        self.post(upload(image_bytes()))
        poll = Poll.objects.get()
        admin = User.objects.create_superuser(email="admin@example.com", username="yonetici", password="Gizli-Parola-2026")
        self.client.force_login(admin)
        response = self.client.post(
            "/admin/polls/poll/",
            {"action": "remove_photos", "_selected_action": [poll.pk]},
            follow=True,
        )
        self.assertContains(response, "1 anketin fotoğrafı kaldırıldı")
        poll.refresh_from_db()
        self.assertFalse(poll.has_image)
        self.assertEqual(PollImage.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("polls:photo", args=[poll.pk])).status_code, 404)


# ============================================== toast bildirimleri + rozet yerleşimi
class ToastTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_message_renders_as_toast_outside_main_content(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("polls:create"), {"question": "Toast?", "option": ["A", "B"]}, follow=True
        )
        html = response.content.decode()
        self.assertIn('class="toasts"', html)
        self.assertIn("data-toast", html)
        self.assertIn("data-toast-close", html)
        self.assertIn("Anketin yayında!", html)
        main = html[html.index("<main"):html.index("</main>")]
        self.assertNotIn("Anketin yayında!", main)  # not a bar inside the content any more
        self.assertNotIn('class="messages"', html)

    def test_error_toast_is_an_alert(self):
        poll = make_poll(self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("polls:vote", args=[poll.pk]), {}, follow=True)
        self.assertContains(response, "toast--error")
        self.assertContains(response, 'data-toast role="alert"')

    def test_delete_message_is_a_toast(self):
        poll = make_poll(self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("polls:delete", args=[poll.pk]), follow=True)
        self.assertContains(response, "toast__text")
        self.assertContains(response, "Anketin silindi.")

    def test_no_toast_container_without_messages(self):
        self.assertNotContains(self.client.get(reverse("polls:home")), "toasts")

    def test_toast_script_exists_and_is_loaded(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("js/toast.js"))
        self.assertContains(self.client.get(reverse("polls:home")), "js/toast.js")

    def test_message_shows_only_once(self):
        self.client.force_login(self.user)
        self.client.post(reverse("polls:create"), {"question": "Bir kez", "option": ["A", "B"]})
        self.client.get(reverse("polls:home"))  # shows the toast
        self.assertNotContains(self.client.get(reverse("polls:home")), "data-toast")


class BadgePlacementTests(TestCase):
    def test_badge_lives_in_the_side_panel_and_main_only_has_the_compact_summary(self):
        user = make_user()
        self.client.force_login(user)
        html = self.client.get(reverse("polls:mine")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        side = html[html.index('aria-label="Popüler anketler"'):]
        self.assertIn("badge-compact", main)
        self.assertNotIn("panel--badge", main)
        self.assertIn("panel--badge", side)
        self.assertLess(side.index("Popüler anketler"), side.index("Rozetim"))  # below the popular list

    def test_other_pages_do_not_get_the_badge_panel(self):
        self.client.force_login(make_user())
        for url in (reverse("polls:home"), reverse("polls:create")):
            self.assertNotContains(self.client.get(url), "panel--badge")
