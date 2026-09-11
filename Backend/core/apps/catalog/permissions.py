from rest_framework.permissions import BasePermission

from apps.users.models import User


class CanEditDataDictionary(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.ADMIN, User.Role.DATA_ENGINEER)
        )
