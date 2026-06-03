"""
VVIT Portal — Core Models

Contains all shared academic domain models:
Branch, Year, Section, Subject, Timetable, Attendance,
Exam, Result, AcademicCalendar, QuestionPaper.

Design notes:
 - db_index=True on all FK and commonly filtered fields for fast lookups.
 - unique_together on Attendance prevents duplicate records.
 - Result.grade is auto-computed on save.
"""

from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
# BRANCH
# ─────────────────────────────────────────────
class Branch(models.Model):
    """Academic department / branch (CSE, ECE, EEE, ME, CE …)."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10,  unique=True)  # e.g., 'CSE'

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"


# ─────────────────────────────────────────────
# YEAR
# ─────────────────────────────────────────────
class Year(models.Model):
    """Academic year level: 1, 2, 3, or 4."""
    YEAR_CHOICES = [(1,'I Year'),(2,'II Year'),(3,'III Year'),(4,'IV Year')]
    year = models.IntegerField(choices=YEAR_CHOICES, unique=True)

    class Meta:
        ordering = ['year']

    def __str__(self):
        return self.get_year_display()


# ─────────────────────────────────────────────
# SECTION
# ─────────────────────────────────────────────
class Section(models.Model):
    """
    A section within a branch + year combination.
    e.g., CSE-II-A, ECE-III-B.
    """
    name   = models.CharField(max_length=5)   # A, B, C …
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, db_index=True)
    year   = models.ForeignKey(Year,   on_delete=models.CASCADE, db_index=True)

    class Meta:
        unique_together = ('name', 'branch', 'year')
        ordering = ['branch', 'year', 'name']

    def __str__(self):
        return f"{self.branch.code}-{self.year.year}-{self.name}"


# ─────────────────────────────────────────────
# SUBJECT
# ─────────────────────────────────────────────
class Subject(models.Model):
    """
    A subject taught in a specific branch, year, and semester.
    faculty is the primary instructor responsible for the subject.
    """
    SEMESTER_CHOICES = [(i, f"Sem {i}") for i in range(1, 9)]

    name     = models.CharField(max_length=150)
    code     = models.CharField(max_length=20,  unique=True, db_index=True)
    branch   = models.ForeignKey(Branch, on_delete=models.CASCADE, db_index=True)
    year     = models.ForeignKey(Year,   on_delete=models.CASCADE, db_index=True)
    semester = models.IntegerField(choices=SEMESTER_CHOICES, db_index=True)
    faculty  = models.ForeignKey(
        'accounts.Faculty', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subjects', db_index=True
    )
    credits  = models.IntegerField(default=3)
    is_lab   = models.BooleanField(default=False)

    class Meta:
        ordering = ['branch', 'year', 'name']
        indexes  = [
            models.Index(fields=['branch', 'year', 'semester']),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


# ─────────────────────────────────────────────
# TIMETABLE ENTRY
# ─────────────────────────────────────────────
class Timetable(models.Model):
    """
    One slot in the section timetable: a (section, day, period) maps
    to a subject and the faculty who teaches it in that slot.
    """
    DAY_CHOICES = [
        ('Monday','Monday'), ('Tuesday','Tuesday'), ('Wednesday','Wednesday'),
        ('Thursday','Thursday'), ('Friday','Friday'), ('Saturday','Saturday'),
    ]
    PERIOD_CHOICES = [(i, f"Period {i}") for i in range(1, 9)]

    section = models.ForeignKey(Section, on_delete=models.CASCADE, db_index=True, related_name='timetable_entries')
    day     = models.CharField(max_length=10, choices=DAY_CHOICES, db_index=True)
    period  = models.IntegerField(choices=PERIOD_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, db_index=True)
    faculty = models.ForeignKey('accounts.Faculty', on_delete=models.SET_NULL, null=True, db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time   = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('section', 'day', 'period')
        ordering = ['day', 'period']
        indexes = [models.Index(fields=['section', 'day'])]

    def __str__(self):
        return f"{self.section} | {self.day} P{self.period} — {self.subject.code}"


# ─────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────
class Attendance(models.Model):
    """
    Attendance record for one student for one timetable slot on one date.
    unique_together ensures no duplicate records.
    last_modified tracks when the record was last changed (faculty audit).
    """
    STATUS_CHOICES = [('P', 'Present'), ('A', 'Absent')]

    student         = models.ForeignKey('accounts.Student', on_delete=models.CASCADE, db_index=True, related_name='attendance_records')
    timetable_entry = models.ForeignKey(Timetable, on_delete=models.CASCADE, db_index=True)
    date            = models.DateField(db_index=True)
    status          = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A')
    last_modified   = models.DateTimeField(auto_now=True)
    marked_by       = models.ForeignKey('accounts.Faculty', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'timetable_entry', 'date')
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['timetable_entry', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.student.roll_number} | {self.date} | {self.timetable_entry.subject.code} | {self.status}"


# ─────────────────────────────────────────────
# EXAM
# ─────────────────────────────────────────────
class Exam(models.Model):
    """
    An examination event (Mid-1, Mid-2, Semester Final, etc.)
    scoped to a branch, year, and semester.
    """
    EXAM_TYPE_CHOICES = [
        ('mid1',  'Mid Term 1'),
        ('mid2',  'Mid Term 2'),
        ('final', 'Semester Final'),
        ('supply','Supplementary'),
    ]

    name     = models.CharField(max_length=100)
    exam_type= models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES, default='mid1')
    semester = models.IntegerField(db_index=True)
    year     = models.ForeignKey(Year,   on_delete=models.CASCADE, db_index=True)
    branch   = models.ForeignKey(Branch, on_delete=models.CASCADE, db_index=True)
    date     = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-date']
        indexes = [models.Index(fields=['branch', 'year', 'semester'])]

    def __str__(self):
        return f"{self.name} — {self.branch.code} Y{self.year.year} Sem{self.semester}"


# ─────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────
class Result(models.Model):
    """
    A student's result for one subject in one exam.
    Grade is auto-computed from marks_obtained / max_marks.
    """
    GRADE_CHOICES = [
        ('S','Outstanding (S)'), ('A','Excellent (A)'), ('B','Very Good (B)'),
        ('C','Good (C)'), ('D','Above Average (D)'), ('E','Average (E)'),
        ('F','Fail (F)'), ('Ab','Absent (Ab)'),
    ]

    student       = models.ForeignKey('accounts.Student', on_delete=models.CASCADE, db_index=True, related_name='results')
    exam          = models.ForeignKey(Exam,    on_delete=models.CASCADE, db_index=True)
    subject       = models.ForeignKey(Subject, on_delete=models.CASCADE, db_index=True)
    marks_obtained= models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_marks     = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    final_total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade         = models.CharField(max_length=3, choices=GRADE_CHOICES, blank=True)

    class Meta:
        unique_together = ('student', 'exam', 'subject')
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['exam', 'subject']),
        ]

    def __str__(self):
        return f"{self.student.roll_number} | {self.exam} | {self.subject.code} | {self.grade}"

    def calculate_grade(self):
        """Auto-calculate grade using the 80/20 Mid + Sem logic."""
        if self.max_marks == 0:
            return 'F'
            
        if self.exam.exam_type in ['mid1', 'mid2']:
            # Mids don't get a final letter grade in this system until the Sem exam.
            return ''
            
        if self.exam.exam_type == 'final':
            # 1. Get Mid 1 and Mid 2 marks
            mid1_pct = 0
            mid2_pct = 0
            
            try:
                m1 = Result.objects.filter(student=self.student, subject=self.subject, exam__exam_type='mid1', exam__semester=self.exam.semester).first()
                if m1 and m1.max_marks > 0:
                    mid1_pct = float(m1.marks_obtained) / float(m1.max_marks) * 100
            except Exception:
                pass
                
            try:
                m2 = Result.objects.filter(student=self.student, subject=self.subject, exam__exam_type='mid2', exam__semester=self.exam.semester).first()
                if m2 and m2.max_marks > 0:
                    mid2_pct = float(m2.marks_obtained) / float(m2.max_marks) * 100
            except Exception:
                pass
                
            # 2. 80/20 Rule for Mids
            top_mid_pct = max(mid1_pct, mid2_pct)
            low_mid_pct = min(mid1_pct, mid2_pct)
            weighted_mid_pct = (top_mid_pct * 0.8) + (low_mid_pct * 0.2)
            mid_contribution = weighted_mid_pct * 0.30  # Max 30 marks
            
            # 3. Sem Rule
            sem_pct = float(self.marks_obtained) / float(self.max_marks) * 100
            sem_contribution = sem_pct * 0.70  # Max 70 marks
            
            # 4. Total and Grading
            total = mid_contribution + sem_contribution
            self.final_total_score = round(total, 2)
            
            if total < 40: return 'F'
            if total <= 50: return 'E'
            if total <= 60: return 'D'
            if total <= 70: return 'C'
            if total <= 80: return 'B'
            if total <= 90: return 'A'
            return 'S'
            
        # Fallback for supplementary or unknown types
        pct = float(self.marks_obtained) / float(self.max_marks) * 100
        if pct < 40: return 'F'
        if pct <= 50: return 'E'
        if pct <= 60: return 'D'
        if pct <= 70: return 'C'
        if pct <= 80: return 'B'
        if pct <= 90: return 'A'
        return 'S'

    def save(self, *args, **kwargs):
        if not self.grade:
            self.grade = self.calculate_grade()
        super().save(*args, **kwargs)

    @property
    def percentage(self):
        if self.max_marks:
            return round(float(self.marks_obtained) / float(self.max_marks) * 100, 2)
        return 0


# ─────────────────────────────────────────────
# ACADEMIC CALENDAR
# ─────────────────────────────────────────────
class AcademicCalendar(models.Model):
    """
    Important academic events: holidays, exams, fests, etc.
    Results are cached at the view layer (5-minute TTL).
    """
    EVENT_TYPE_CHOICES = [
        ('holiday',  'Holiday'),
        ('exam',     'Examination'),
        ('event',    'University Event'),
        ('deadline', 'Deadline'),
        ('other',    'Other'),
    ]

    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date        = models.DateField(db_index=True)
    event_type  = models.CharField(max_length=15, choices=EVENT_TYPE_CHOICES, default='other', db_index=True)
    branch      = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="Leave blank for all branches")
    year        = models.ForeignKey(Year,   on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="Leave blank for all years")

    class Meta:
        ordering = ['date']
        indexes  = [models.Index(fields=['date', 'event_type'])]

    def __str__(self):
        return f"{self.date} | {self.title}"


# ─────────────────────────────────────────────
# QUESTION PAPER
# ─────────────────────────────────────────────
class QuestionPaper(models.Model):
    """
    Past examination question papers stored as uploaded PDF files.
    Students can filter by subject, year, semester and download.
    """
    title       = models.CharField(max_length=200)
    subject     = models.ForeignKey(Subject, on_delete=models.CASCADE, db_index=True, related_name='question_papers')
    year        = models.IntegerField(db_index=True, help_text="Academic year the paper was set, e.g. 2023")
    semester    = models.IntegerField(db_index=True)
    file        = models.FileField(upload_to='question_papers/')
    upload_date = models.DateField(auto_now_add=True)
    uploaded_by = models.ForeignKey('accounts.Faculty', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-year', '-semester']
        indexes  = [models.Index(fields=['subject', 'year', 'semester'])]

    def __str__(self):
        return f"{self.title} ({self.subject.code} | {self.year} Sem-{self.semester})"


# ─────────────────────────────────────────────
# RESULT RELEASE
# ─────────────────────────────────────────────
class ResultRelease(models.Model):
    """
    Admin publishes an exam's results.
    Once released=True, students can see results and emails are sent.
    """
    exam        = models.OneToOneField(Exam, on_delete=models.CASCADE, related_name='release')
    released    = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    email_sent  = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Result Release'

    def __str__(self):
        status = 'Released' if self.released else 'Not Released'
        return f"{self.exam.name} — {status}"


# ─────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────
class Notification(models.Model):
    """
    Admin-created notifications pushed to users.

    Targeting:
      target_all=True          → every authenticated user
      target_role='student'    → all students
      target_role='faculty'    → all faculty
      target_branch            → a specific branch (combined with target_role)
      target_user              → a single specific user
    """

    TYPE_RESULT       = 'result'
    TYPE_ATTENDANCE   = 'attendance'
    TYPE_ANNOUNCEMENT = 'announcement'
    TYPE_EXAM         = 'exam'
    TYPE_HOLIDAY      = 'holiday'
    TYPE_SYSTEM       = 'system'

    NOTIF_TYPES = [
        (TYPE_RESULT,       'Result Released'),
        (TYPE_ATTENDANCE,   'Attendance Alert'),
        (TYPE_ANNOUNCEMENT, 'Announcement'),
        (TYPE_EXAM,         'Exam Notice'),
        (TYPE_HOLIDAY,      'Holiday Notice'),
        (TYPE_SYSTEM,       'System'),
    ]

    PRIORITY_LOW    = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH   = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW,    'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH,   'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]

    # Content
    title    = models.CharField(max_length=200)
    message  = models.TextField()
    notif_type = models.CharField(max_length=20, choices=NOTIF_TYPES, default=TYPE_ANNOUNCEMENT, db_index=True)
    priority   = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    link       = models.CharField(max_length=300, blank=True, help_text='Optional URL to navigate to when clicked')

    # Targeting
    target_all    = models.BooleanField(default=True, help_text='Send to every user')
    target_role   = models.CharField(max_length=30, blank=True,
                                     help_text="'student', 'faculty', 'admin', etc. — leave blank for all")
    target_branch = models.ForeignKey(Branch, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='notifications')
    target_section = models.ForeignKey(Section, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='notifications')
    target_user   = models.ForeignKey('accounts.User', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='targeted_notifications')

    # Metadata
    created_by = models.ForeignKey('accounts.User', null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='sent_notifications')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True,
                                      help_text='Notification hidden after this date/time')
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notif_type_display()}] {self.title}"

    @property
    def icon(self):
        """FontAwesome icon class for each type."""
        return {
            self.TYPE_RESULT:       'fa-chart-bar',
            self.TYPE_ATTENDANCE:   'fa-clipboard-check',
            self.TYPE_ANNOUNCEMENT: 'fa-bullhorn',
            self.TYPE_EXAM:         'fa-file-alt',
            self.TYPE_HOLIDAY:      'fa-umbrella-beach',
            self.TYPE_SYSTEM:       'fa-cog',
        }.get(self.notif_type, 'fa-bell')

    @property
    def color_class(self):
        """CSS colour name for each type."""
        return {
            self.TYPE_RESULT:       'notif-green',
            self.TYPE_ATTENDANCE:   'notif-orange',
            self.TYPE_ANNOUNCEMENT: 'notif-blue',
            self.TYPE_EXAM:         'notif-purple',
            self.TYPE_HOLIDAY:      'notif-teal',
            self.TYPE_SYSTEM:       'notif-grey',
        }.get(self.notif_type, 'notif-grey')


class NotificationRead(models.Model):
    """Tracks which notifications a user has already read."""
    user         = models.ForeignKey('accounts.User', on_delete=models.CASCADE,
                                     related_name='notification_reads')
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE,
                                     related_name='reads')
    read_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notification')
        verbose_name    = 'Notification Read'

    def __str__(self):
        return f"{self.user.username} read '{self.notification.title}'"
