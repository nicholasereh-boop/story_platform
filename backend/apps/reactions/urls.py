from django.urls import path

from . import views as v

urlpatterns = [
    path("stories/<slug:slug>/like/", v.StoryLikeView.as_view(), name="story-like"),
    path("stories/<slug:slug>/likes/", v.StoryLikesView.as_view(), name="story-likes"),
]
