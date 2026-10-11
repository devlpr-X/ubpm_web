"""URL routing for the mobile (Expo) customer API — mounted at /api/v1/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "api"

router = DefaultRouter()
router.register("categories", views.DeviceCategoryViewSet, basename="category")
router.register("branches", views.BranchViewSet, basename="branch")
router.register("partners", views.PartnerLocationViewSet, basename="partner")
router.register("content", views.SiteContentViewSet, basename="content")
router.register("requests", views.IntakeRequestViewSet, basename="request")

# Staff / admin router (mounted under /staff/).
staff_router = DefaultRouter()
staff_router.register("requests", views.StaffRequestViewSet, basename="staff-request")
staff_router.register("pickups", views.PickupViewSet, basename="staff-pickup")

urlpatterns = [
    # Liveness probe (мобайл аппын домайн fallback + PaaS healthcheck)
    path("health/", views.HealthView.as_view(), name="health"),
    # Auth (JWT)
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
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
    # Түгээмэл асуултууд (вэбийн /faq/-тэй нэг эх сурвалж)
    path("faq/", views.FaqView.as_view(), name="faq"),
    # Staff / admin (dashboard parity with the web)
    path("staff/dashboard/", views.StaffDashboardView.as_view(), name="staff_dashboard"),
    path("staff/staff-users/", views.StaffUserListView.as_view(), name="staff_users"),
    path("staff/export/", views.StaffExportView.as_view(), name="staff_export"),
    path("staff/pickup-queue/", views.PickupQueueView.as_view(), name="staff_pickup_queue"),
    path("staff/email-status/", views.EmailStatusView.as_view(), name="staff_email_status"),
    path("staff/chats/", views.StaffChatListView.as_view(), name="staff_chats"),
    path(
        "staff/chats/<int:conversation_id>/",
        views.StaffChatDetailView.as_view(),
        name="staff_chat_detail",
    ),
    # Push мэдэгдлийн token бүртгэх / устгах (апп)
    path("push/devices/", views.PushDeviceView.as_view(), name="push_devices"),
    # Чат (хэрэглэгч ↔ ажилтан)
    path("chat/", views.ChatView.as_view(), name="chat"),
    path("chat/unread/", views.ChatUnreadView.as_view(), name="chat_unread"),
    path("chat/<int:conversation_id>/messages/", views.ChatMessagesView.as_view(), name="chat_messages"),
    path("staff/", include(staff_router.urls)),
    # Resources
    path("", include(router.urls)),
]
