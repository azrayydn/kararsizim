from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()


@register.filter
def ago(value):
    """Short Turkish relative time: 'az önce', '5 dakika önce', '3 gün önce' ..."""
    if not value:
        return ""
    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return "az önce"
    if seconds < 3600:
        return f"{seconds // 60} dakika önce"
    if seconds < 86400:
        return f"{seconds // 3600} saat önce"
    if seconds < 7 * 86400:
        return f"{seconds // 86400} gün önce"
    return date_format(timezone.localtime(value), "j F Y")


# ---- side panels (shown on wide screens only; rendered lazily by these tags)
from django.contrib.auth import get_user_model  # noqa: E402
from django.db.models import Count  # noqa: E402

from ..models import Poll, Vote  # noqa: E402


@register.inclusion_tag("polls/_side_stats.html")
def side_stats():
    return {
        "polls": Poll.objects.count(),
        "votes": Vote.objects.count(),
        "members": get_user_model().objects.count(),
    }


@register.inclusion_tag("polls/_side_popular.html")
def side_popular():
    popular = (
        Poll.objects.annotate(total_votes=Count("votes"))
        .filter(total_votes__gt=0)
        .order_by("-total_votes", "-created_at", "-id")[:5]
    )
    return {"popular": popular}
