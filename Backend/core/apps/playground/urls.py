from django.urls import path

from .views import PlaygroundChatView

urlpatterns = [
    path("chat/", PlaygroundChatView.as_view(), name="playground-chat"),
]
