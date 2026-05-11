"""VVIT Portal — Accounts URL patterns"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('redirect/', views.role_redirect, name='redirect'),
    path('',          views.login_view,    name='root'),
]
