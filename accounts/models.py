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
        ('deo',           'Data Entry Operator'),
    ]

    role  = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', db_index=True)
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
    )
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_by_name = models.CharField(max_length=150, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

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
            'hod':           'hod:dashboard',
            'lab_technician':'faculty:dashboard',
            'admin':         'admin_dashboard:dashboard',
            'deo':           'deo:dashboard',
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
    parent_name  = models.CharField(max_length=100, blank=True, null=True)
    parent_occupation = models.CharField(max_length=100, blank=True, null=True)
    parent_mobile = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
    )
    personal_mobile = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
    )
    gender       = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], blank=True, null=True)
    caste        = models.CharField(max_length=50, blank=True, null=True)
    religion     = models.CharField(max_length=50, blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    present_address   = models.TextField(blank=True, null=True)
    fees_pending = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Pending fees amount in INR")
    fees_updated_at   = models.DateTimeField(blank=True, null=True)


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

    @property
    def calculate_attendance_pct(self):
        """Calculate overall attendance percentage dynamically."""
        from core.models import Attendance
        records = Attendance.objects.filter(student=self)
        total = records.count()
        if total == 0:
            return 0.0
        present = records.filter(status='P').count()
        return round(present / total * 100, 1)

    def calculate_cgpa(self):
        """Calculate CGPA for the student across all released final results."""
        from core.models import Result
        grade_points = {
            'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5,
            'F': 0, 'Ab': 0
        }
        cgpa_results = Result.objects.filter(
            student=self,
            exam__exam_type='final',
            exam__release__released=True
        ).select_related('subject')
        
        cgpa_points = 0
        cgpa_credits = 0
        for r in cgpa_results:
            if r.grade and r.grade not in ['CP', 'NCP']:
                points = grade_points.get(r.grade, 0)
                cgpa_points += points * r.subject.credits
                cgpa_credits += r.subject.credits
                
        return round(cgpa_points / cgpa_credits, 2) if cgpa_credits > 0 else 0.0

    def get_backlogs(self):
        """
        Retrieve active backlog results for this student.
        Returns the list of Result objects for subjects where the latest released final exam result
        is failing or absent (grade F, Ab, AB, FAIL or marks < 40).
        """
        from core.models import Result
        released_results = Result.objects.filter(
            student=self,
            exam__exam_type__in=['final', 'sem', 'SEM'],
            exam__release__released=True,
        ).select_related('subject', 'exam').order_by('subject_id', '-exam__date', '-id')

        active_backlogs = []
        seen_subjects = set()

        for res in released_results:
            if res.subject_id in seen_subjects:
                continue
            seen_subjects.add(res.subject_id)

            if (res.grade in ['F', 'Ab', 'AB', 'FAIL']) or (res.marks_obtained and float(res.marks_obtained) < 40):
                active_backlogs.append(res)

        return active_backlogs

    @property
    def total_backlogs_count(self):
        """Return total active backlog count for the student."""
        return len(self.get_backlogs())


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


# ─────────────────────────────────────────────
# DEO PROFILE
# ─────────────────────────────────────────────
class DEOProfile(models.Model):
    """
    Profile for Data Entry Operator.
    Assigned to a specific branch/department.
    """
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='deo_profile', db_index=True)
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    branch      = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'DEO Profile'
        verbose_name_plural = 'DEO Profiles'

    def __str__(self):
        return f"DEO: {self.employee_id} — {self.user.get_full_name() or self.user.username}"


# ─────────────────────────────────────────────
# ACHIEVEMENT
# ─────────────────────────────────────────────
class Achievement(models.Model):
    """
    Academic, Co-curricular, Extra-curricular achievements of students or faculty.
    Verified by HOD or Admin.
    """
    CATEGORY_CHOICES = [
        ('curricular', 'Curricular'),
        ('cocurricular', 'Co-curricular'),
    ]
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements', db_index=True)
    title         = models.CharField(max_length=200)
    description   = models.TextField()
    category      = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='curricular', db_index=True)
    date_achieved = models.DateField(db_index=True)
    is_verified   = models.BooleanField(default=False, db_index=True)
    verified_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_achievements')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
        ordering = ['-date_achieved']

    def __str__(self):
        return f"{self.user.username} — {self.title} ({self.category})"


# ─────────────────────────────────────────────
# FACULTY LEAVE REQUEST
# ─────────────────────────────────────────────
class FacultyLeaveRequest(models.Model):
    """
    Faculty Leave Request submitted to HOD and Admin.
    Either HOD or Admin can approve or reject the request.
    """
    LEAVE_TYPE_CHOICES = [
        ('casual',    'Casual Leave (CL)'),
        ('sick',      'Sick Leave (SL)'),
        ('duty',      'On Duty (OD)'),
        ('earned',    'Earned Leave (EL)'),
        ('maternity', 'Maternity / Paternity Leave'),
        ('other',     'Other Leave'),
    ]

    STATUS_CHOICES = [
        ('pending',  'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    faculty          = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='leave_requests', db_index=True)
    leave_type       = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='casual', db_index=True)
    start_date       = models.DateField(db_index=True)
    end_date         = models.DateField(db_index=True)
    reason           = models.TextField()
    substitute_notes = models.TextField(blank=True, null=True, help_text="Class substitution or arrangement notes")
    
    status           = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    action_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='actioned_leaves')
    action_at        = models.DateTimeField(null=True, blank=True)
    admin_remarks    = models.TextField(blank=True, null=True, help_text="Remarks by HOD or Admin")
    
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Faculty Leave Request'
        verbose_name_plural = 'Faculty Leave Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.faculty.full_name} — {self.get_leave_type_display()} ({self.start_date} to {self.end_date}) [{self.status.upper()}]"

    @property
    def total_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 1
