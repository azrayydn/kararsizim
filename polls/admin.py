from django.contrib import admin

from .models import Option, Poll, PollImage, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "created_at", "closes_at", "has_image")
    actions = ["remove_photos"]
    readonly_fields = ("settled_at", "winner")
    search_fields = ("question", "author__username")
    list_select_related = ("author",)
    inlines = [OptionInline]

    @admin.action(description="Seçili anketlerin fotoğrafını kaldır")
    def remove_photos(self, request, queryset):
        PollImage.objects.filter(poll__in=queryset).delete()
        count = queryset.update(has_image=False)
        self.message_user(request, f"{count} anketin fotoğrafı kaldırıldı.")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "option", "user", "created_at")
    list_select_related = ("poll", "option", "user")
    search_fields = ("poll__question", "user__username")
