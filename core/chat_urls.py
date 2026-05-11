from django.urls import path
from core import chat_views as views

app_name = 'chat'

urlpatterns = [
    path('',        views.chat,        name='chat'),
    path('context/',views.bot_context, name='context'),
]
