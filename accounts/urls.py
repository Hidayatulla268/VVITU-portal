"""VVIT Portal — Accounts URL patterns"""

from django.urls import path
from . import views
from . import profile_detail_views

app_name = 'accounts'

urlpatterns = [
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('redirect/', views.role_redirect, name='redirect'),
    path('set-password/', views.set_password, name='set_password'),
    path('profile/',  views.profile_view,  name='profile'),
    path('students/<int:pk>/detail/', profile_detail_views.student_detail_view, name='student_detail'),
    path('faculty/<int:pk>/detail/', profile_detail_views.faculty_detail_view, name='faculty_detail'),
    path('',          views.login_view,    name='root'),
]
