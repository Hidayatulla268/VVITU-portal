"""VVIT Portal — Student URL patterns"""

from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('',                   views.dashboard,        name='dashboard'),
    path('class-diary/',       views.class_diary,      name='class_diary'),
    path('syllabus/',          views.syllabus_coverage,name='syllabus_coverage'),
    path('syllabus/<int:subject_id>/', views.syllabus_coverage, name='syllabus_coverage_subject'),
    path('timetable/',         views.timetable,        name='timetable'),
    path('results/',           views.results,          name='results'),
    path('academic-calendar/', views.academic_calendar,name='academic_calendar'),
    path('question-papers/',   views.question_papers,  name='question_papers'),
    path('achievements/add/',  views.add_achievement,  name='add_achievement'),
    path('counselling-report/', views.counselling_report, name='counselling_report'),
    path('counselling-report/pdf/', views.download_counselling_report_pdf, name='download_counselling_report_pdf'),
]
