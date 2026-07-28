"""Custom DRF permissions for the API."""

from rest_framework.permissions import BasePermission


class IsStaffRole(BasePermission):
    """Allow only staff-role users (ADMIN / MANAGER / OPERATOR) or superusers.

    Mirrors the web dashboard's `staff_required` decorator
    (apps/accounts/views.py) so the mobile admin surface matches the web.
    """

    message = "Энэ үйлдлийг зөвхөн ажилтан гүйцэтгэх боломжтой."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (getattr(user, "is_staff_role", False) or user.is_superuser)
        )
