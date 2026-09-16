from django.urls import path
from . import views

app_name = 'deo'

urlpatterns = [
    path('',                         views.dashboard,          name='dashboard'),
    path('students/',                views.manage_students,    name='manage_students'),
    path('students/add/',            views.add_student,        name='add_student'),
    path('students/<int:pk>/edit/',  views.edit_student,       name='edit_student'),
    
    # Scoped Attendance and 1-Day Edit Constraint
    path('attendance/',              views.attendance_list,    name='attendance_list'),
    path('attendance/<int:pk>/edit/',views.edit_attendance,    name='edit_attendance'),
    
    # Scoped Marks Upload
    path('upload-marks/',            views.upload_marks,       name='upload_marks'),
    
    # Scoped Fees Management
    path('fees/',                    views.manage_fees,          name='manage_fees'),

    # Timetable
    path('timetable/',               views.manage_timetable,     name='manage_timetable'),
    path('timetable/section/<int:section_id>/', views.section_timetable, name='section_timetable'),
    path('timetable/faculty/<int:faculty_id>/', views.faculty_timetable, name='faculty_timetable'),
    path('timetable/export-pdf/<int:section_id>/', views.export_timetable_pdf, name='export_timetable_pdf'),
]
