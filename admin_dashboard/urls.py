"""VVIT Portal — Admin Dashboard URL patterns"""

from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('',                         views.dashboard,            name='dashboard'),

    # Students
    path('students/',                views.manage_students,      name='manage_students'),
    path('students/add/',            views.add_student,          name='add_student'),
    path('students/bulk-upload/',    views.bulk_upload_students, name='bulk_upload_students'),
    path('students/sample-csv/',     views.download_sample_students_csv, name='sample_students_csv'),
    path('students/<int:pk>/edit/',  views.edit_student,         name='edit_student'),
    path('students/<int:pk>/delete/',views.delete_student,       name='delete_student'),

    # Faculty
    path('faculty/',                 views.manage_faculty,       name='manage_faculty'),
    path('faculty/add/',             views.add_faculty,          name='add_faculty'),
    path('faculty/<int:pk>/edit/',   views.edit_faculty,         name='edit_faculty'),
    path('faculty/<int:pk>/delete/', views.delete_faculty,       name='delete_faculty'),

    # Assignments
    path('assign-class-teacher/',    views.assign_class_teacher, name='assign_class_teacher'),
    path('assign-counsellor/',       views.assign_counsellor,    name='assign_counsellor'),

    # Timetable
    path('timetable/',               views.manage_timetable,     name='manage_timetable'),

    # Results
    path('bulk-upload-results/',     views.bulk_upload_results,  name='bulk_upload_results'),
    path('sample-results-csv/',      views.download_sample_results_csv, name='sample_results_csv'),
    path('add-results/',             views.add_results,          name='add_results'),
    path('release-results/',         views.release_results,      name='release_results'),

    # Attendance override and reports
    path('attendance/',              views.attendance_list,      name='attendance_list'),
    path('attendance/<int:pk>/edit/',views.edit_attendance,      name='edit_attendance'),
    path('attendance/report/',       views.admin_attendance_report, name='admin_attendance_report'),
]
