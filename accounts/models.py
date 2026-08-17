"""
VVIT Portal — Accounts Models

Custom User model with role-based access control.
Student and Faculty profiles linked via OneToOneField.
"""

import secrets
import string
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


def generate_secure_temp_password(length=12):
    """
    Generates a cryptographically secure, random temporary password
    satisfying uppercase, lowercase, digit, and special character requirements.
    """
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(chars) for _ in range(max(length - 4, 4))]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


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
        ('curricular', 'Academic / Curricular'),
        ('cocurricular', 'Co-curricular'),
        ('extracurricular', 'Extra-curricular & Sports'),
        ('college', 'College & Institutional Achievement'),
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
        ('casual',       'Casual Leave (CL)'),
        ('sick',         'Sick Leave (SL)'),
        ('half_day_an',  'Afternoon Half Day (AN) — 0.5 Day'),
        ('half_day_fn',  'Morning Half Day (FN) — 0.5 Day'),
        ('duty',         'On Duty (OD)'),
        ('earned',       'Earned Leave (EL)'),
        ('maternity',    'Maternity / Paternity Leave'),
        ('other',        'Other Leave'),
    ]

    SESSION_CHOICES = [
        ('full', 'Full Day'),
        ('an',   'Afternoon Half Day (AN)'),
        ('fn',   'Morning Half Day (FN)'),
    ]

    STATUS_CHOICES = [
        ('pending',  'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    faculty          = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='leave_requests', db_index=True)
    leave_type       = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='casual', db_index=True)
    session          = models.CharField(max_length=10, choices=SESSION_CHOICES, default='full', db_index=True)
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
    def is_half_day(self):
        return self.session in ('an', 'fn') or self.leave_type in ('half_day_an', 'half_day_fn')

    @property
    def total_days(self):
        if self.start_date and self.end_date:
            if self.is_half_day and self.start_date == self.end_date:
                return 0.5
            return (self.end_date - self.start_date).days + 1
        return 0


# ─────────────────────────────────────────────
# STUDENT FEE STRUCTURE & PAYMENTS
# ─────────────────────────────────────────────
class StudentFee(models.Model):
    """
    Detailed Fee Structure and Payment Status for a student.
    Includes College Tuition, Hostel, Bus, NBA, Exam, Book Bank, and Misc fees.
    """
    FEE_STATUS_CHOICES = [
        ('paid',    'Fully Paid'),
        ('partial', 'Partially Paid'),
        ('pending', 'Pending / Unpaid'),
        ('overdue', 'Overdue'),
    ]

    student          = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_records', db_index=True)
    academic_year    = models.ForeignKey('core.Year', on_delete=models.CASCADE, db_index=True)
    
    # Detailed Breakdown Categories (Amounts in INR)
    college_fee      = models.DecimalField(max_digits=12, decimal_places=2, default=70000.00, verbose_name="College / Tuition Fee")
    hostel_fee       = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Hostel Fee (Optional)")
    bus_fee          = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Bus / Transport Fee (Optional)")
    nba_fee          = models.DecimalField(max_digits=12, decimal_places=2, default=3000.00, verbose_name="NBA Accreditation Fee")
    exam_fee         = models.DecimalField(max_digits=12, decimal_places=2, default=2500.00, verbose_name="Exam Fee")
    book_bank_fee    = models.DecimalField(max_digits=12, decimal_places=2, default=1500.00, verbose_name="Book Bank / Library Fee")
    other_fee        = models.DecimalField(max_digits=12, decimal_places=2, default=1000.00, verbose_name="Other / Misc Fee")
    
    # Calculations & Payment Tracking
    total_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=78000.00, help_text="Auto-calculated total sum of all fee components")
    amount_paid      = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Total amount paid by student so far")
    due_amount       = models.DecimalField(max_digits=12, decimal_places=2, default=78000.00, help_text="Remaining balance due")
    status           = models.CharField(max_length=15, choices=FEE_STATUS_CHOICES, default='pending', db_index=True)
    due_date         = models.DateField(null=True, blank=True)
    
    remarks          = models.TextField(blank=True, null=True, help_text="Admin/HOD/DEO notes, scholarship details or payment reference")
    updated_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_fees')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'academic_year')
        ordering = ['-academic_year__year', 'student__roll_number']

    def __str__(self):
        return f"{self.student.roll_number} — Y{self.academic_year.year} Fees: Total ₹{self.total_fee_amount} (Paid ₹{self.amount_paid})"

    def save(self, *args, **kwargs):
        def clamp(val, max_val=10000000.0):
            try:
                v = float(val or 0)
                if v < 0: return 0.0
                if v > max_val: return max_val
                return round(v, 2)
            except (ValueError, TypeError, OverflowError):
                return 0.0

        col = clamp(self.college_fee)
        hos = clamp(self.hostel_fee)
        bus = clamp(self.bus_fee)
        nba = clamp(self.nba_fee)
        exm = clamp(self.exam_fee)
        bbk = clamp(self.book_bank_fee)
        oth = clamp(self.other_fee)
        paid = clamp(self.amount_paid)

        self.college_fee   = col
        self.hostel_fee    = hos
        self.bus_fee       = bus
        self.nba_fee       = nba
        self.exam_fee      = exm
        self.book_bank_fee = bbk
        self.other_fee     = oth
        self.amount_paid   = paid

        self.total_fee_amount = clamp(col + hos + bus + nba + exm + bbk + oth, max_val=70000000.0)
        self.due_amount       = clamp(max(0, self.total_fee_amount - paid))

        # Rule: If all fee components are zero OR balance due is <= 0, status is 'paid' (Fully Paid)
        if self.total_fee_amount == 0 or self.due_amount <= 0:
            self.status = 'paid'
        elif paid > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'

        super().save(*args, **kwargs)
