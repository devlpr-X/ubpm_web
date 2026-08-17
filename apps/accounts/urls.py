from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.UbpmLoginView.as_view(), name="login"),
    # Google Identity Services-ийн буцаасан ID token-ийг хүлээж авна (fetch, JSON).
    path("google/", views.GoogleLoginView.as_view(), name="google_login"),
    path("logout/", views.UbpmLogoutView.as_view(), name="logout"),
    path("signup/", views.CustomerSignupView.as_view(), name="signup"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("my-requests/", views.MyRequestsView.as_view(), name="my_requests"),
    # Password reset by emailed 4-digit code (2 steps)
    path("password-reset/", views.PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password-reset/verify/",
        views.PasswordResetVerifyView.as_view(),
        name="password_reset_verify",
    ),
]
