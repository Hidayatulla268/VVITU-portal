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
]
