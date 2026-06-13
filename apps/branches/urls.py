from django.urls import path

from . import views

app_name = "branches"

urlpatterns = [
    path("", views.branch_list, name="list"),
    path("<slug:code>/edit/", views.branch_edit, name="edit"),
    path("<slug:code>/", views.branch_detail, name="detail"),
]
