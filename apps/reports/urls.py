from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("requests/", views.request_list, name="request_list"),
    path("requests/<str:code>/", views.request_detail, name="request_detail"),
    path("requests/<str:code>/quote/", views.add_quote, name="add_quote"),
    path("requests/<str:code>/status/", views.change_status, name="change_status"),
    path("requests/<str:code>/assign/", views.assign, name="assign"),
    path("requests/<str:code>/pickup/", views.schedule_pickup, name="schedule_pickup"),
    path("delivery/", views.delivery_map, name="delivery"),
    path("pickups/", views.pickup_list, name="pickup_list"),
    path("pickups/<int:pk>/", views.pickup_detail, name="pickup_detail"),
    path("reports/", views.reports, name="reports"),
    path("reports/export/", views.export, name="export"),
    # Email тохиргоог браузераас оношлох (зөвхөн ADMIN).
    path("email-status/", views.email_status, name="email_status"),
]
