from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Student, Faculty, DEOProfile

class StudentInline(admin.StackedInline):
    model = Student
    extra = 0
    verbose_name_plural = 'Student Profile Details'
    fk_name = 'user'

class FacultyInline(admin.StackedInline):
    model = Faculty
    extra = 0
    verbose_name_plural = 'Faculty Profile Details'
    fk_name = 'user'

class DEOProfileInline(admin.StackedInline):
    model = DEOProfile
    extra = 0
    verbose_name_plural = 'DEO Profile Details'
    fk_name = 'user'

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('VVIT Info', {'fields': ('role', 'phone', 'profile_picture')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('VVIT Info', {'fields': ('role', 'phone')}),
    )
    list_display  = ('username', 'get_full_name', 'email', 'role', 'phone', 'is_active')
    list_filter   = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    inlines = [StudentInline, FacultyInline, DEOProfileInline]

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display  = ('roll_number', 'user', 'branch', 'year', 'section', 'is_active')
    list_filter   = ('branch', 'year', 'is_active')
    search_fields = ('roll_number', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user', 'class_teacher', 'counsellor')

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display  = ('employee_id', 'user', 'department', 'designation', 'is_active')
    list_filter   = ('department', 'is_active')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name')

@admin.register(DEOProfile)
class DEOProfileAdmin(admin.ModelAdmin):
    list_display  = ('employee_id', 'user', 'branch', 'is_active')
    list_filter   = ('branch', 'is_active')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name')
