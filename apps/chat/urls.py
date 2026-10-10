from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.customer_chat, name="customer"),
    path("unread/", views.unread, name="unread"),
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/<int:conversation_id>/", views.staff_thread, name="staff_thread"),
    path("<int:conversation_id>/poll/", views.poll, name="poll"),
    path("<int:conversation_id>/send/", views.send, name="send"),
]
