from django.urls import path
from core import notification_views as views

app_name = 'notifications'

urlpatterns = [
    path('',                views.notification_centre,  name='centre'),
    path('api/',            views.notifications_api,    name='api'),
    path('count/',          views.notification_count,   name='count'),
    path('mark-read/',      views.mark_read,            name='mark_read'),
    path('mark-all/',       views.mark_all_read,        name='mark_all'),
    path('manage/',         views.manage_notices,       name='manage'),
    path('create/',         views.create_notification,  name='create'),
    path('edit/<int:pk>/',  views.edit_notification,    name='edit'),
    path('delete/<int:pk>/',views.delete_notification,  name='delete'),
]
