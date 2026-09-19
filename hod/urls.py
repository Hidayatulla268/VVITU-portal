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
    path('timetable/section/<int:section_id>/', views.edit_timetable, name='section_timetable'),
    path('timetable/ajax-check-clash/', views.ajax_check_timetable_clash, name='ajax_check_timetable_clash'),
    path('timetable/upload-api/',    views.upload_timetable_api,       name='upload_timetable_api'),
    path('timetable/export-pdf/<int:section_id>/', views.export_timetable_pdf, name='export_timetable_pdf'),
    path('timetable/faculty/<int:faculty_id>/', views.faculty_timetable_view, name='faculty_timetable'),
    path('verify-achievements/',     views.verify_achievements,       name='verify_achievements'),
    path('verify-achievement/<int:pk>/<str:action_type>/', views.verify_achievement_action, name='verify_achievement_action'),
    
    # Branch Scoped CRUD
    path('students/',                views.manage_students,           name='manage_students'),
    path('students/add/',            views.add_student,               name='add_student'),
    path('students/<int:pk>/edit/',  views.edit_student,              name='edit_student'),
    path('students/<int:pk>/delete/',views.delete_student,            name='delete_student'),
    path('students/<int:student_id>/counselling-report/',     views.student_counselling_report,            name='student_counselling_report'),
    path('students/<int:student_id>/counselling-report/pdf/', views.download_student_counselling_report_pdf, name='download_student_counselling_report_pdf'),
    path('faculty/',                 views.manage_faculty,            name='manage_faculty'),
    path('faculty/add/',             views.add_faculty,               name='add_faculty'),
    path('faculty/<int:pk>/edit/',   views.edit_faculty,              name='edit_faculty'),
    path('faculty-attendance/',      views.faculty_attendance,        name='faculty_attendance'),
    
    # Scoped Attendance Override
    path('attendance/',              views.attendance_list,           name='attendance_list'),
    path('attendance/<int:pk>/edit/',views.edit_attendance,           name='edit_attendance'),
    path('release-results/',         views.release_results,           name='release_results'),

    # Branch Scoped Subjects CRUD
    path('subjects/',                views.manage_subjects,           name='manage_subjects'),
    path('subjects/add/',            views.add_subject,               name='add_subject'),
    path('subjects/<int:pk>/delete/',views.delete_subject,            name='delete_subject'),

    # Branch Scoped Marks CRUD (Mid 1 & Mid 2)
    path('mid-marks/',               views.upload_mid_marks,          name='upload_mid_marks'),

    # Leave Management
    path('leave-requests/',               views.manage_leave_requests, name='manage_leave_requests'),
    path('leave-requests/<int:pk>/<str:action>/', views.action_leave_request, name='action_leave_request'),
    path('leave-requests/cancel/<int:pk>/', views.cancel_leave_request, name='cancel_leave_request'),
    # Fee Management
    path('fees/',                    views.manage_fees,               name='manage_fees'),
    # Class Transfer Audit & Proxy Management
    path('class-transfers/',         views.manage_class_transfers,            name='manage_class_transfers'),
    path('ajax/branch-timetable/',   views.ajax_get_branch_timetable_slots,  name='ajax_branch_timetable'),
    path('ajax/free-faculty/',       views.ajax_get_free_faculty,             name='ajax_free_faculty'),
    # Class Diary & Syllabus Coverage
    path('class-diary/',             views.class_diary_coverage,              name='class_diary_coverage'),
    path('syllabus/',                views.manage_subject_syllabus,           name='manage_subject_syllabus'),
    path('syllabus/<int:subject_id>/', views.manage_subject_syllabus,          name='manage_subject_syllabus_subject'),
    path('exam-schedules/',          views.manage_exam_schedules,             name='manage_exam_schedules'),
    # Detention, Readmission & Low Attendance
    path('detention-readmissions/',  views.manage_detention_readmissions,     name='manage_detention_readmissions'),
    path('detention-readmissions/<int:pk>/<str:action>/', views.action_readmission_request, name='action_readmission_request'),
    path('student-leaves/',          views.manage_student_leaves,             name='manage_student_leaves'),
    path('student-leaves/<int:pk>/<str:action>/', views.action_student_leave, name='action_student_leave'),
    path('low-attendance-center/',   views.low_attendance_action_center,      name='low_attendance_action_center'),
    # Faculty Class Attendance & Conduction Audit Table
    path('faculty-class-audit/',     views.faculty_class_attendance_audit,     name='faculty_class_audit'),
    path('class-attendance/<int:timetable_id>/<str:date>/', views.class_session_audit_detail, name='class_attendance_detail'),

    # Student Feedback Management & Document Upload (HOD)
    path('feedback/',                     views.manage_feedback_forms, name='manage_feedback_forms'),
    path('feedback/create/',              views.create_feedback_form,  name='create_feedback_form'),
    path('feedback/extract-api/',         views.extract_feedback_document_api, name='extract_feedback_document_api'),
    path('feedback/<int:form_id>/edit/',  views.edit_feedback_form,    name='edit_feedback_form'),
    path('feedback/<int:form_id>/analytics/', views.feedback_analytics, name='feedback_analytics'),
    path('feedback/<int:form_id>/analytics/pdf/', views.export_feedback_analytics_pdf, name='export_feedback_analytics_pdf'),
    path('feedback/<int:form_id>/blank-pdf/', views.download_blank_feedback_pdf, name='download_blank_feedback_pdf'),
    path('feedback/<int:form_id>/submission/<int:submission_id>/', views.view_student_feedback_summary, name='view_student_feedback_summary'),
    path('feedback/<int:form_id>/submission/<int:submission_id>/pdf/', views.download_student_feedback_pdf, name='download_student_feedback_pdf'),
    path('feedback/<int:form_id>/toggle-status/', views.toggle_feedback_status, name='toggle_feedback_status'),
    path('feedback/<int:form_id>/delete/', views.delete_feedback_form, name='delete_feedback_form'),
]


