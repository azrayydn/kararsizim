from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .badges import attach_author_badges, badges_for_users, profile_for
from .forms import PollForm
from .insights import summarize
from .models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    OPTION_MAX_LENGTH,
    QUESTION_MAX_LENGTH,
    URGENT_MINUTES,
    Poll,
    PollImage,
    Vote,
)

PAGE_SIZE = 15


def percentages(counts):
    """Whole-number percentages that always add up to 100 (largest remainder)."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    raw = [count * 100 / total for count in counts]
    result = [int(value) for value in raw]
    leftover = 100 - sum(result)
    by_remainder = sorted(range(len(counts)), key=lambda i: raw[i] - result[i], reverse=True)
    for index in by_remainder[:leftover]:
        result[index] += 1
    return result


def _feed(polls):
    return (
        polls.select_related("author")
        .prefetch_related("options")
        .annotate(total_votes=Count("votes"))
        # Explicit: Django ignores Meta.ordering once the query is grouped (annotate + Count).
        .order_by("-created_at", "-id")
    )


def _page(request, polls):
    page_obj = Paginator(_feed(polls), PAGE_SIZE).get_page(request.GET.get("page"))
    page_obj.object_list = attach_author_badges(page_obj.object_list)
    return page_obj


def home(request):
    return render(request, "polls/home.html", {"page_obj": _page(request, Poll.objects.all())})


@login_required
def my_polls(request):
    page_obj = _page(request, Poll.objects.filter(author=request.user))
    return render(
        request,
        "polls/my_polls.html",
        {"page_obj": page_obj, "badge_profile": profile_for(request.user)},
    )


def poll_detail(request, pk):
    poll = get_object_or_404(Poll.objects.select_related("author"), pk=pk)
    options = list(poll.options.annotate(vote_count=Count("votes")))
    counts = [option.vote_count for option in options]
    total = sum(counts)

    my_option_id = None
    if request.user.is_authenticated:
        my_option_id = (
            Vote.objects.filter(poll=poll, user=request.user)
            .values_list("option_id", flat=True)
            .first()
        )
    has_voted = my_option_id is not None

    blind = poll.is_blind  # open Acil Karar: the standings must not leak into the page
    closed_urgent = poll.is_urgent and poll.is_closed

    context = {
        "poll": poll,
        "total": total,
        "has_voted": has_voted,
        "blind": blind,
        "closed_urgent": closed_urgent,
        "clock": poll.clock,
        "seconds_left": poll.seconds_left,
        "can_vote": request.user.is_authenticated and not has_voted and not closed_urgent,
        "is_owner": request.user.is_authenticated and poll.author_id == request.user.pk,
        "author_badge": badges_for_users({poll.author_id}).get(poll.author_id),
        "insight": None,
    }

    if blind:
        # Only the option texts (and whether one is yours) are sent to the browser.
        context["blind_rows"] = [
            {"option": option, "is_mine": option.pk == my_option_id} for option in options
        ]
    else:
        shares = percentages(counts)
        top = max(counts) if total else None
        rows = [
            {
                "option": option,
                "count": count,
                "pct": pct,
                "is_mine": option.pk == my_option_id,
                "is_winner": total > 0 and count == top,
            }
            for option, count, pct in zip(options, counts, shares)
        ]
        context["rows"] = rows
        context["insight"] = summarize(rows, total, has_voted=has_voted, closed=closed_urgent)

    return render(request, "polls/poll_detail.html", context)


@require_POST
def poll_vote(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    detail_url = reverse("polls:detail", args=[poll.pk])

    if not request.user.is_authenticated:
        # Send guests to log in and bring them back to the poll page (a GET page).
        return redirect_to_login(detail_url)

    if poll.is_urgent and poll.is_closed:
        messages.error(request, "Bu Acil Karar'ın süresi doldu, oylama kapandı.")
        return redirect(detail_url)

    option_id = request.POST.get("option", "")
    option = poll.options.filter(pk=option_id).first() if option_id.isdigit() else None
    if option is None:
        messages.error(request, "Bir seçenek seçmelisin.")
        return redirect(detail_url)

    try:
        with transaction.atomic():
            Vote.objects.create(poll=poll, option=option, user=request.user)
    except IntegrityError:
        messages.error(request, "Bu ankete zaten oy verdin.")
    else:
        if poll.is_blind:
            messages.success(request, "Oyun kaydedildi! Sonuç süre dolunca açıklanacak ⏳")
        else:
            messages.success(request, "Oyun kaydedildi! ✅")
    return redirect(detail_url)


def poll_photo(request, pk):
    data = PollImage.objects.filter(poll_id=pk).values_list("data", flat=True).first()
    if data is None:
        raise Http404
    response = HttpResponse(bytes(data), content_type="image/webp")
    # Short CDN cache: a photo removed by a moderator disappears within the hour.
    response["Cache-Control"] = "public, max-age=86400, s-maxage=3600"
    return response


@require_POST
def poll_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect_to_login(reverse("polls:detail", args=[pk]))
    # Only the author can delete. Anyone else gets a plain 404, same as a missing poll.
    poll = get_object_or_404(Poll, pk=pk, author=request.user)
    poll.delete()
    messages.success(request, "Anketin silindi.")
    return redirect("polls:mine")


@login_required
def poll_create(request):
    form = PollForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        poll = form.save(author=request.user)
        if poll.is_urgent:
            messages.success(request, f"Acil Karar başladı! {URGENT_MINUTES} dakikan var ⏱")
        else:
            messages.success(request, "Anketin yayında! 🎉")
        return redirect("polls:detail", pk=poll.pk)
    context = {
        "form": form,
        "min_options": MIN_OPTIONS,
        "max_options": MAX_OPTIONS,
        "option_max": OPTION_MAX_LENGTH,
        "question_max": QUESTION_MAX_LENGTH,
        "urgent_minutes": URGENT_MINUTES,
    }
    return render(request, "polls/poll_form.html", context)
