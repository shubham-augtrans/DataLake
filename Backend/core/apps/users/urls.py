from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, UserPreferencesView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/preferences/", UserPreferencesView.as_view(), name="user-preferences"),
    # Lets the frontend silently exchange a still-valid refresh token for a
    # new access token instead of hard-logging the user out the moment the
    # 1-hour access token expires mid-session.
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]