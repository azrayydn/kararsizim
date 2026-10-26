"""Badges for people who vote with the community on "Acil Karar" polls.

How it works
------------
* Only closed Acil Karar polls count, and only when they ended with at least MIN_VOTES votes
  and one clear winner (no tie). Results of an open Acil Karar poll are hidden, so nobody can
  simply copy the current leader to farm badges.
* A vote "hits" when the voter picked the winning option. Voting on your own poll never counts.
* A badge needs both enough counted votes and a high enough hit rate.
"""
from collections import namedtuple

from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Poll, Vote

MIN_VOTES = 5  # an Acil Karar needs at least this many votes to count

Badge = namedtuple("Badge", "key name emoji min_votes min_rate")

# Highest first.
BADGES = (
    Badge("guru", "Guru", "🧙", 40, 0.75),
    Badge("master", "Master Karar Verici", "🏅", 20, 0.65),
    Badge("verici", "Karar Verici", "🎯", 8, 0.55),
    Badge("cirak", "Karar Çırağı", "🐣", 3, 0.0),
)


def settle_due_polls():
    """Fix the winner of every Acil Karar that has just closed (idempotent, runs lazily)."""
    now = timezone.now()
    due = Poll.objects.filter(closes_at__lte=now, settled_at__isnull=True).annotate(total=Count("votes"))
    for poll in list(due):
        winner = None
        if poll.total >= MIN_VOTES:
            top = list(poll.options.annotate(vote_count=Count("votes")).order_by("-vote_count", "position")[:2])
            if len(top) == 1 or (len(top) == 2 and top[0].vote_count > top[1].vote_count):
                winner = top[0]
        Poll.objects.filter(pk=poll.pk, settled_at__isnull=True).update(settled_at=now, winner=winner)


def user_stats(user_ids):
    """{user_id: (counted_votes, hits)} for users who have at least one counted vote."""
    rows = (
        Vote.objects.filter(user_id__in=list(user_ids), poll__winner__isnull=False)
        .exclude(poll__author_id=F("user_id"))
        .values("user_id")
        .annotate(total=Count("id"), hits=Count("id", filter=Q(option_id=F("poll__winner_id"))))
    )
    return {row["user_id"]: (row["total"], row["hits"]) for row in rows}


def badge_for(total, hits):
    rate = hits / total if total else 0
    for badge in BADGES:
        if total >= badge.min_votes and rate >= badge.min_rate:
            return badge
    return None


def badges_for_users(user_ids):
    settle_due_polls()
    stats = user_stats(user_ids)
    result = {}
    for user_id, (total, hits) in stats.items():
        badge = badge_for(total, hits)
        if badge:
            result[user_id] = badge
    return result


def attach_author_badges(polls):
    """Set `poll.author_badge` on every poll with one extra query for the whole list."""
    polls = list(polls)
    badges = badges_for_users({poll.author_id for poll in polls})
    for poll in polls:
        poll.author_badge = badges.get(poll.author_id)
    return polls


def profile_for(user):
    """Everything the 'Anketlerim' badge card needs."""
    settle_due_polls()
    total, hits = user_stats([user.pk]).get(user.pk, (0, 0))
    rate = round(hits * 100 / total) if total else 0
    current = badge_for(total, hits)
    higher = [b for b in BADGES if current is None or BADGES.index(b) < BADGES.index(current)]
    next_badge = higher[-1] if higher else None  # the closest tier above the current one
    return {
        "total": total,
        "hits": hits,
        "rate": rate,
        "current": current,
        "next": next_badge,
        "next_rate_percent": round(next_badge.min_rate * 100) if next_badge else 0,
        "tiers": list(reversed(BADGES)),
    }
