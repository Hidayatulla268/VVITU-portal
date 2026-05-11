"""VVIT Portal — Student URL patterns"""

from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('',                   views.dashboard,        name='dashboard'),
    path('timetable/',         views.timetable,        name='timetable'),
    path('results/',           views.results,          name='results'),
    path('academic-calendar/', views.academic_calendar,name='academic_calendar'),
    path('question-papers/',   views.question_papers,  name='question_papers'),
]
