import math

from django.conf import settings
from django.db import models
from django.utils import timezone

QUESTION_MAX_LENGTH = 200
OPTION_MAX_LENGTH = 100
MIN_OPTIONS = 2
MAX_OPTIONS = 5
URGENT_MINUTES = 5  # length of an "Acil Karar" poll


class Poll(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls"
    )
    question = models.CharField("soru", max_length=QUESTION_MAX_LENGTH)
    created_at = models.DateTimeField("oluşturulma", auto_now_add=True, db_index=True)

    # "Acil Karar" polls: voting closes at `closes_at`, results stay hidden until then.
    closes_at = models.DateTimeField("kapanış", null=True, blank=True)
    # Filled lazily once a closed poll is "settled" (see polls/badges.py). `winner` stays empty
    # when the poll had too few votes or ended in a tie; such polls do not count for badges.
    settled_at = models.DateTimeField("kesinleşme", null=True, blank=True)
    winner = models.ForeignKey(
        "Option", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # The picture itself lives in PollImage so normal poll queries never load image bytes.
    has_image = models.BooleanField("fotoğraf var", default=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    def __str__(self):
        return self.question

    @property
    def is_urgent(self):
        return self.closes_at is not None

    @property
    def is_closed(self):
        return self.closes_at is not None and timezone.now() >= self.closes_at

    @property
    def is_blind(self):
        """Urgent and still open: nobody sees the standings until the timer ends."""
        return self.is_urgent and not self.is_closed

    @property
    def seconds_left(self):
        if self.closes_at is None:
            return 0
        return max(0, math.ceil((self.closes_at - timezone.now()).total_seconds()))

    @property
    def clock(self):
        seconds = self.seconds_left
        return f"{seconds // 60}:{seconds % 60:02d}"


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField("seçenek", max_length=OPTION_MAX_LENGTH)
    position = models.PositiveSmallIntegerField("sıra", default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"
        constraints = [
            models.UniqueConstraint(fields=["poll", "position"], name="unique_option_position_per_poll"),
        ]

    def __str__(self):
        return self.text


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes"
    )
    created_at = models.DateTimeField("oy zamanı", auto_now_add=True)

    class Meta:
        verbose_name = "oy"
        verbose_name_plural = "oylar"
        constraints = [
            # One person, one vote per poll.
            models.UniqueConstraint(fields=["poll", "user"], name="one_vote_per_user_per_poll"),
        ]

    def __str__(self):
        return f"{self.user} → {self.option}"


class PollImage(models.Model):
    """One optional, already resized WebP photo per poll (see polls/images.py)."""

    poll = models.OneToOneField(Poll, on_delete=models.CASCADE, related_name="image")
    data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "anket fotoğrafı"
        verbose_name_plural = "anket fotoğrafları"
