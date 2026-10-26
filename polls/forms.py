from datetime import timedelta

from django import forms
from django.db import transaction
from django.utils import timezone

from .images import process_upload
from .models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    OPTION_MAX_LENGTH,
    QUESTION_MAX_LENGTH,
    URGENT_MINUTES,
    Option,
    Poll,
    PollImage,
)


def _squash(text):
    """Trim and collapse any run of whitespace (incl. newlines) into one space."""
    return " ".join((text or "").split())


class PollForm(forms.Form):
    question = forms.CharField(
        label="Ne konuda kararsızsın?",
        max_length=QUESTION_MAX_LENGTH,
        error_messages={
            "required": "Sorunu yazmalısın.",
            "max_length": f"Soru en fazla {QUESTION_MAX_LENGTH} karakter olabilir.",
        },
        widget=forms.Textarea(
            attrs={
                "class": "field__input field__input--question",
                "rows": 2,
                "maxlength": QUESTION_MAX_LENGTH,
                "placeholder": "Bugün sinemaya mı gitsem, restorana mı?",
                "autofocus": True,
            }
        ),
    )

    image = forms.FileField(
        required=False,
        label="Fotoğraf",
        widget=forms.FileInput(
            attrs={
                "class": "field__file",
                "accept": "image/jpeg,image/png,image/webp",
                "data-photo-input": True,
            }
        ),
    )

    urgent = forms.BooleanField(
        required=False,
        label=f"Acil Karar yap ({URGENT_MINUTES} dakika)",
        widget=forms.CheckboxInput(attrs={"class": "check__input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The options come in as repeated <input name="option"> fields.
        if self.is_bound:
            raw = self.data.getlist("option")
        else:
            raw = []
        # Always show at least MIN_OPTIONS rows; never trust more than a few extra.
        padded = (list(raw) + [""] * MIN_OPTIONS)[: max(len(raw), MIN_OPTIONS)]
        self.option_values = padded[:MAX_OPTIONS]

    @property
    def had_upload(self):
        return self.is_bound and bool(self.files.get("image"))

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        return process_upload(upload) if upload else None

    def clean_question(self):
        return _squash(self.cleaned_data["question"])

    def clean(self):
        cleaned = super().clean()
        raw = self.data.getlist("option") if self.is_bound else []

        if len(raw) > MAX_OPTIONS * 3:
            # Someone is tampering with the form; keep the message simple.
            self.add_error(None, f"En fazla {MAX_OPTIONS} seçenek ekleyebilirsin.")
            return cleaned

        texts = [_squash(item) for item in raw]
        filled = [text for text in texts if text]

        if len(filled) < MIN_OPTIONS:
            self.add_error(None, f"En az {MIN_OPTIONS} seçenek yazmalısın.")
        elif len(filled) > MAX_OPTIONS:
            self.add_error(None, f"En fazla {MAX_OPTIONS} seçenek ekleyebilirsin.")
        elif any(len(text) > OPTION_MAX_LENGTH for text in filled):
            self.add_error(None, f"Her seçenek en fazla {OPTION_MAX_LENGTH} karakter olabilir.")
        elif len({text.casefold() for text in filled}) != len(filled):
            self.add_error(None, "Aynı seçeneği iki kez yazmışsın.")
        else:
            cleaned["options"] = filled
        return cleaned

    @transaction.atomic
    def save(self, author):
        closes_at = None
        if self.cleaned_data.get("urgent"):
            closes_at = timezone.now() + timedelta(minutes=URGENT_MINUTES)
        image = self.cleaned_data.get("image")
        poll = Poll.objects.create(
            author=author,
            question=self.cleaned_data["question"],
            closes_at=closes_at,
            has_image=bool(image),
        )
        if image:
            PollImage.objects.create(poll=poll, data=image)
        Option.objects.bulk_create(
            [
                Option(poll=poll, text=text, position=index)
                for index, text in enumerate(self.cleaned_data["options"])
            ]
        )
        return poll
