from django.contrib import admin
from .models import (Branch, Year, Section, Subject, Timetable,
                     Attendance, Exam, Result, AcademicCalendar, QuestionPaper)

admin.site.register(Branch)
from .models import ResultRelease
admin.site.register(ResultRelease)
admin.site.register(Year)

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'branch', 'year')
    list_filter  = ('branch', 'year')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'branch', 'year', 'semester', 'faculty')
    list_filter   = ('branch', 'year', 'semester')
    search_fields = ('code', 'name')

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('section', 'day', 'period', 'subject', 'faculty')
    list_filter  = ('section__branch', 'day')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display  = ('student', 'timetable_entry', 'date', 'status', 'last_modified')
    list_filter   = ('status', 'date')
    search_fields = ('student__roll_number',)
    date_hierarchy = 'date'

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'branch', 'year', 'semester', 'date')
    list_filter  = ('branch', 'year', 'exam_type')

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display  = ('student', 'exam', 'subject', 'marks_obtained', 'max_marks', 'grade')
    list_filter   = ('exam', 'grade')
    search_fields = ('student__roll_number',)

@admin.register(AcademicCalendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'event_type', 'branch')
    list_filter  = ('event_type', 'branch')
    date_hierarchy = 'date'

@admin.register(QuestionPaper)
class QuestionPaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'year', 'semester', 'upload_date')
    list_filter  = ('subject__branch', 'year', 'semester')

from .models import Notification, NotificationRead

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('title','notif_type','priority','target_all','target_role','is_active','created_at')
    list_filter   = ('notif_type','priority','is_active','target_all','target_role')
    search_fields = ('title','message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at','created_by')
    def save_model(self, request, obj, form, change):
        if not obj.pk: obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display  = ('user','notification','read_at')
    list_filter   = ('notification__notif_type',)
    search_fields = ('user__username','notification__title')
    readonly_fields = ('read_at',)
