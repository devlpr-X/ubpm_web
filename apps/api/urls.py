"""URL routing for the mobile (Expo) customer API — mounted at /api/v1/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = "api"

router = DefaultRouter()
router.register("categories", views.DeviceCategoryViewSet, basename="category")
router.register("branches", views.BranchViewSet, basename="branch")
router.register("partners", views.PartnerLocationViewSet, basename="partner")
router.register("requests", views.IntakeRequestViewSet, basename="request")

urlpatterns = [
    # Auth (JWT)
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/google/", views.GoogleAuthView.as_view(), name="google"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    # Password reset by emailed 4-digit code
    path(
        "auth/password/request-code/",
        views.PasswordResetRequestView.as_view(),
        name="password_request_code",
    ),
    path(
        "auth/password/reset/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset",
    ),
    # Public tracking
    path("track/<uuid:token>/", views.TrackView.as_view(), name="track"),
    # Resources
    path("", include(router.urls)),
]
