from django.urls import path
from . import views

app_name = 'hod'

urlpatterns = [
    path('',                         views.dashboard,                 name='dashboard'),
    path('notice/create/',           views.create_notice,             name='create_notice'),
    path('assign-teacher/',          views.assign_teacher,            name='assign_teacher'),
    path('subject-mapping/',         views.subject_mapping,           name='subject_mapping'),
    path('timetable/',               views.manage_timetable,          name='manage_timetable'),
    path('timetable/edit/<int:section_id>/', views.edit_timetable,    name='edit_timetable'),
    path('verify-achievements/',     views.verify_achievements,       name='verify_achievements'),
    path('verify-achievement/<int:pk>/<str:action_type>/', views.verify_achievement_action, name='verify_achievement_action'),
    
    # Branch Scoped CRUD
    path('students/',                views.manage_students,           name='manage_students'),
    path('students/add/',            views.add_student,               name='add_student'),
    path('students/<int:pk>/edit/',  views.edit_student,              name='edit_student'),
    path('students/<int:pk>/delete/',views.delete_student,            name='delete_student'),
    path('faculty/',                 views.manage_faculty,            name='manage_faculty'),
    path('faculty/add/',             views.add_faculty,               name='add_faculty'),
    path('faculty/<int:pk>/edit/',   views.edit_faculty,              name='edit_faculty'),
    
    # Scoped Attendance Override
    path('attendance/',              views.attendance_list,           name='attendance_list'),
    path('attendance/<int:pk>/edit/',views.edit_attendance,           name='edit_attendance'),
    path('release-results/',         views.release_results,           name='release_results'),

    # Branch Scoped Subjects CRUD
    path('subjects/',                views.manage_subjects,           name='manage_subjects'),
    path('subjects/add/',            views.add_subject,               name='add_subject'),
    path('subjects/<int:pk>/delete/',views.delete_subject,            name='delete_subject'),
]
