from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Student, Faculty

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
