from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, UserPreferencesView, UserViewSet

router = DefaultRouter()
router.register(r"", UserViewSet, basename="user")

urlpatterns = [
    # Literal paths must stay ahead of the router include below - Django
    # matches urlpatterns top-to-bottom, so these exact segments resolve
    # here rather than being swallowed by the router's <pk> lookup.
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/preferences/", UserPreferencesView.as_view(), name="user-preferences"),
    # Lets the frontend silently exchange a still-valid refresh token for a
    # new access token instead of hard-logging the user out the moment the
    # 1-hour access token expires mid-session.
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]