from django.urls import path

from .views import AboutView, ContactView, FaqView, HomeView, PrivacyView, content_edit

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("faq/", FaqView.as_view(), name="faq"),
    # Privacy policy — required by Google Play. Served both with and without a
    # trailing slash so the exact URL given to Play Console resolves directly.
    path("privacy", PrivacyView.as_view(), name="privacy"),
    path("privacy/", PrivacyView.as_view()),
    path("content/<slug:key>/edit/", content_edit, name="content_edit"),
]
