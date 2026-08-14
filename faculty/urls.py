"""VVIT Portal — Faculty URL patterns"""

from django.urls import path
from . import views

app_name = 'faculty'

urlpatterns = [
    path('',                     views.dashboard,          name='dashboard'),
    path('mark-attendance/',     views.mark_attendance,    name='mark_attendance'),
    path('class-diary/',         views.class_diary,        name='class_diary'),
    path('my-attendance/',       views.my_attendance,      name='my_attendance'),
    path('transfer-class/',      views.transfer_class,     name='transfer_class'),
    path('reports/',             views.reports,            name='reports'),
    path('export/excel/',        views.export_excel,       name='export_excel'),
    path('export/pdf/',          views.export_pdf,         name='export_pdf'),
    path('counselled-students/', views.counselled_students,name='counselled_students'),
    path('student-results/',     views.student_results,    name='student_results'),
    path('upload-marks/',        views.upload_marks,       name='upload_marks'),
    path('achievements/add/',    views.add_achievement,    name='add_achievement'),

    # Leave Requests
    path('leave-requests/',               views.leave_requests,      name='leave_requests'),
    path('leave-requests/cancel/<int:pk>/', views.cancel_leave_request, name='cancel_leave_request'),

    # AJAX endpoints
    path('ajax/students/',       views.ajax_get_students,     name='ajax_students'),
    path('ajax/timetable/',      views.ajax_get_timetable,    name='ajax_timetable'),
    path('ajax/free-faculty/',   views.ajax_get_free_faculty, name='ajax_free_faculty'),
]
