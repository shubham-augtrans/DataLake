from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsAdmin
from .serializers import (
    LoginSerializer,
    UserPreferencesSerializer,
    UserSerializer,
    UserWriteSerializer,
)


class LoginView(APIView):

    permission_classes = []

    def post(self, request):

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role,
                    "active_bi_tool": user.active_bi_tool,
                },
            },
            status=status.HTTP_200_OK,
        )


class UserPreferencesView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserPreferencesSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserPreferencesSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):

    queryset = User.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer


class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:
            refresh_token = request.data.get("refresh") or request.data.get("refresh_token")

            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception as e:
                    # If token blacklist is disabled or token invalid, proceed with successful logout response
                    pass

            return Response(
                {"message": "Logged out successfully."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"message": "Error logging out.", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )