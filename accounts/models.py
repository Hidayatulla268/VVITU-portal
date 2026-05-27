"""
VVIT Portal — Accounts Models

Custom User model with role-based access control.
Student and Faculty profiles linked via OneToOneField.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


# ─────────────────────────────────────────────
# CUSTOM USER
# ─────────────────────────────────────────────
class User(AbstractUser):
    """
    Extended user model.  The `role` field drives dashboard routing and
    middleware access control.  Username is in VVIT format: 24BQ1A4942.
    """
    ROLE_CHOICES = [
        ('student',       'Student'),
        ('faculty',       'Faculty'),
        ('admin',         'Admin'),
        ('hod',           'Head of Department'),
        ('lab_technician','Lab Technician'),
    ]

    role  = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', db_index=True)
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
    )
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['username']),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    def get_dashboard_url(self):
        """Return the correct dashboard URL based on role."""
        from django.urls import reverse
        role_map = {
            'student':       'student:dashboard',
            'faculty':       'faculty:dashboard',
            'hod':           'faculty:dashboard',
            'lab_technician':'faculty:dashboard',
            'admin':         'admin_dashboard:dashboard',
        }
        return reverse(role_map.get(self.role, 'accounts:login'))


# ─────────────────────────────────────────────
# STUDENT PROFILE
# ─────────────────────────────────────────────
class Student(models.Model):
    """
    Extended profile for a student.  Linked to User 1-to-1.
    roll_number is the unique college roll (e.g., 24BQ1A4942).
    class_teacher and counsellor are Faculty instances.
    """
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile', db_index=True)
    roll_number  = models.CharField(max_length=20, unique=True, db_index=True)
    branch       = models.ForeignKey('core.Branch',   on_delete=models.SET_NULL, null=True, db_index=True)
    year         = models.ForeignKey('core.Year',     on_delete=models.SET_NULL, null=True, db_index=True)
    section      = models.ForeignKey('core.Section',  on_delete=models.SET_NULL, null=True, db_index=True)
    class_teacher= models.ForeignKey('Faculty', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_students',    db_index=True)
    counsellor   = models.ForeignKey('Faculty', on_delete=models.SET_NULL, null=True, blank=True, related_name='counselled_students', db_index=True)
    admission_year = models.IntegerField(default=2024)
    is_active    = models.BooleanField(default=True)
    is_first_login = models.BooleanField(default=True)


    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        indexes = [
            models.Index(fields=['roll_number']),
            models.Index(fields=['branch', 'year', 'section']),
        ]

    def __str__(self):
        return f"{self.roll_number} — {self.user.get_full_name()}"

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone


# ─────────────────────────────────────────────
# FACULTY PROFILE
# ─────────────────────────────────────────────
class Faculty(models.Model):
    """
    Extended profile for faculty, HOD, and lab technicians.
    employee_id is the unique staff ID.
    """
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='faculty_profile', db_index=True)
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    department  = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, null=True, db_index=True)
    designation = models.CharField(max_length=100, blank=True)
    joining_date= models.DateField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Faculty'
        verbose_name_plural = 'Faculty Members'
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return f"{self.employee_id} — {self.user.get_full_name()}"

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def phone(self):
        return self.user.phone
