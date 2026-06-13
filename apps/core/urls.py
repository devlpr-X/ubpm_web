from django.urls import path

from .views import AboutView, ContactView, FaqView, HomeView, content_edit

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("faq/", FaqView.as_view(), name="faq"),
    path("content/<slug:key>/edit/", content_edit, name="content_edit"),
]
