"""VVIT Portal — Faculty URL patterns"""

from django.urls import path
from . import views

app_name = 'faculty'

urlpatterns = [
    path('',                     views.dashboard,          name='dashboard'),
    path('mark-attendance/',     views.mark_attendance,    name='mark_attendance'),
    path('reports/',             views.reports,            name='reports'),
    path('export/excel/',        views.export_excel,       name='export_excel'),
    path('export/pdf/',          views.export_pdf,         name='export_pdf'),
    path('counselled-students/', views.counselled_students,name='counselled_students'),
    path('student-results/',     views.student_results,    name='student_results'),

    # AJAX endpoints
    path('ajax/students/',       views.ajax_get_students,  name='ajax_students'),
    path('ajax/timetable/',      views.ajax_get_timetable, name='ajax_timetable'),
]
