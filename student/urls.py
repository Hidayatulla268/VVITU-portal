"""VVIT Portal — Student URL patterns"""

from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('',                   views.dashboard,        name='dashboard'),
    path('attendance/',        views.attendance_log,   name='attendance'),
    path('my-attendance/',     views.attendance_log,   name='my_attendance'),
    path('class-diary/',       views.class_diary,      name='class_diary'),
    path('syllabus/',          views.syllabus_coverage,name='syllabus_coverage'),
    path('syllabus/<int:subject_id>/', views.syllabus_coverage, name='syllabus_coverage_subject'),
    path('timetable/',         views.timetable,        name='timetable'),
    path('results/',           views.results,          name='results'),
    path('academic-calendar/', views.academic_calendar,name='academic_calendar'),
    path('question-papers/',   views.question_papers,  name='question_papers'),
    path('question-papers/<int:paper_id>/download/', views.download_question_paper, name='download_question_paper'),
    path('achievements/add/',  views.add_achievement,  name='add_achievement'),
    path('counselling-report/', views.counselling_report, name='counselling_report'),
    path('counselling-report/pdf/', views.download_counselling_report_pdf, name='download_counselling_report_pdf'),
    path('attendance/pdf/',    views.download_monthly_attendance_pdf, name='download_monthly_attendance_pdf'),
    path('results/grade-card/pdf/', views.download_grade_card_pdf, name='download_grade_card_pdf'),
    path('leave-od/apply/',    views.apply_leave_od,    name='apply_leave_od'),
    path('readmission/apply/', views.apply_readmission, name='apply_readmission'),
]
