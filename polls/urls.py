from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.home, name="home"),
    path("anket/yeni/", views.poll_create, name="create"),
    path("anket/<int:pk>/", views.poll_detail, name="detail"),
    path("anket/<int:pk>/oy/", views.poll_vote, name="vote"),
    path("anket/<int:pk>/foto/", views.poll_photo, name="photo"),
    path("anket/<int:pk>/sil/", views.poll_delete, name="delete"),
    path("ben/", views.my_polls, name="mine"),
]
