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
    path('students/<int:student_id>/counselling-report/',     views.student_counselling_report,            name='student_counselling_report'),
    path('students/<int:student_id>/counselling-report/pdf/', views.download_student_counselling_report_pdf, name='download_student_counselling_report_pdf'),

    # Faculty
    path('faculty/',                 views.manage_faculty,       name='manage_faculty'),
    path('faculty/add/',             views.add_faculty,          name='add_faculty'),
    path('faculty/<int:pk>/edit/',   views.edit_faculty,         name='edit_faculty'),
    path('faculty/<int:pk>/delete/', views.delete_faculty,       name='delete_faculty'),
    path('faculty-attendance/',      views.faculty_attendance_report, name='faculty_attendance_report'),

    # Assignments
    path('assign-class-teacher/',    views.assign_class_teacher, name='assign_class_teacher'),
    path('assign-counsellor/',       views.assign_counsellor,    name='assign_counsellor'),

    # Timetable
    path('timetable/',               views.manage_timetable,     name='manage_timetable'),
    path('timetable/edit/<int:section_id>/', views.edit_timetable, name='edit_timetable'),
    path('timetable/section/<int:section_id>/', views.edit_timetable, name='section_timetable'),
    path('timetable/ajax-check-clash/', views.ajax_check_timetable_clash, name='ajax_check_timetable_clash'),
    path('timetable/upload-api/',    views.upload_timetable_api,  name='upload_timetable_api'),
    path('timetable/export-pdf/<int:section_id>/', views.export_timetable_pdf, name='export_timetable_pdf'),
    path('timetable/faculty/<int:faculty_id>/', views.faculty_timetable_view, name='faculty_timetable'),

    # Sections Management
    path('sections/',                views.manage_sections,      name='manage_sections'),
    path('sections/<int:pk>/delete/',views.delete_section,       name='delete_section'),

    # Results
    path('bulk-upload-results/',     views.bulk_upload_results,  name='bulk_upload_results'),
    path('sample-results-csv/',      views.download_sample_results_csv, name='sample_results_csv'),
    path('add-results/',             views.add_results,          name='add_results'),
    path('release-results/',         views.release_results,      name='release_results'),

    # Attendance override and reports
    path('attendance/',              views.attendance_list,      name='attendance_list'),
    path('attendance/<int:pk>/edit/',views.edit_attendance,      name='edit_attendance'),
    path('attendance/report/',       views.admin_attendance_report, name='admin_attendance_report'),
    path('faculty-class-audit/',     views.faculty_class_attendance_audit, name='faculty_class_audit'),
    path('class-attendance/<int:timetable_id>/<str:date>/', views.class_session_audit_detail, name='class_attendance_detail'),
    path('faculty-class-history/',   views.faculty_class_history, name='faculty_class_history'),
    path('class-transfers/',         views.faculty_class_history, name='manage_class_transfers'),
    path('class-diary/',             views.class_diary_coverage,  name='class_diary_coverage'),
    path('syllabus/',                views.manage_subject_syllabus, name='manage_subject_syllabus'),
    path('exam-schedules/',          views.manage_exam_schedules, name='manage_exam_schedules'),
    path('academic-calendar/',       views.academic_calendar,     name='academic_calendar'),
    path('ajax/branch-timetable/',   views.ajax_get_all_timetable_slots, name='ajax_branch_timetable'),

    path('ajax/free-faculty/',       views.ajax_get_free_faculty, name='ajax_free_faculty'),


    # Subjects
    path('subjects/',                views.manage_subjects,      name='manage_subjects'),
    path('subjects/add/',            views.add_subject,          name='add_subject'),
    path('subjects/<int:pk>/delete/',views.delete_subject,       name='delete_subject'),

    # Backups & PDF Export
    path('backups/',                 views.backup_list,          name='backup_list'),
    path('backups/create/',          views.create_backup,        name='create_backup'),
    path('backups/download/<int:pk>/', views.download_backup,    name='download_backup'),
    path('backups/restore/<int:pk>/', views.restore_backup,      name='restore_backup'),
    path('backups/delete/<int:pk>/',  views.delete_backup,        name='delete_backup'),
    path('export/database-pdf/',     views.export_database_pdf,  name='export_database_pdf'),
    path('export/results-pdf/',      views.export_student_results_pdf, name='export_student_results_pdf'),

    # Leave Management
    path('leave-requests/',               views.manage_leave_requests, name='manage_leave_requests'),
    path('leave-requests/<int:pk>/<str:action>/', views.action_leave_request, name='action_leave_request'),

    # College & System Achievements
    path('achievements/',                 views.manage_achievements,   name='manage_achievements'),
    path('achievements/verify/<int:pk>/<str:action>/', views.action_achievement, name='action_achievement'),
    path('achievements/delete/<int:pk>/', views.delete_achievement,   name='delete_achievement'),

    # Student Fee Management
    path('fees/',                         views.manage_fees,           name='manage_fees'),

    # Detention & Readmission Ratification
    path('detention-readmissions/',       views.manage_detention_readmissions, name='manage_detention_readmissions'),
    path('detention-readmissions/<int:pk>/<str:action>/', views.action_readmission_request, name='action_readmission_request'),

    # Student Feedback Management & Document Upload
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


