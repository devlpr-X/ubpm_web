from django.urls import path

from .views import (
    AboutView,
    AccountDeleteView,
    AppView,
    ContactView,
    FaqView,
    HomeView,
    PrivacyView,
    content_edit,
    favicon,
    footer_edit,
    home_category_add,
    home_category_delete,
)

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("favicon.ico", favicon, name="favicon"),
    path("about/", AboutView.as_view(), name="about"),
    path("app/", AppView.as_view(), name="app"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("faq/", FaqView.as_view(), name="faq"),
    # Privacy policy — required by Google Play. Served both with and without a
    # trailing slash so the exact URL given to Play Console resolves directly.
    path("privacy", PrivacyView.as_view(), name="privacy"),
    path("privacy/", PrivacyView.as_view()),
    # Account/data deletion — required by Google Play. Both slash variants.
    path("account/delete", AccountDeleteView.as_view(), name="account_delete"),
    path("account/delete/", AccountDeleteView.as_view()),
    path("content/categories/add/", home_category_add, name="home_category_add"),
    path(
        "content/categories/<int:pk>/delete/", home_category_delete, name="home_category_delete"
    ),
    path("content/footer/edit/", footer_edit, name="footer_edit"),
    path("content/<slug:key>/edit/", content_edit, name="content_edit"),
]
