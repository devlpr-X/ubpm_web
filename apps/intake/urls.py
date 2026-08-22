from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("new/", views.RequestNewView.as_view(), name="request_new"),
    path("submitted/<uuid:token>/", views.RequestSubmittedView.as_view(), name="submitted"),
    path("track/", views.TrackEntryView.as_view(), name="track"),
    path("track/<uuid:token>/", views.TrackDetailView.as_view(), name="track_detail"),
    path("track/<uuid:token>/accept/", views.track_accept, name="track_accept"),
]
