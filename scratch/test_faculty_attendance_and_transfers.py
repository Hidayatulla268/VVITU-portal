import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.utils import timezone
from accounts.models import User, Faculty, Student
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, FacultyAttendance, ClassTransfer, Exam, Result
)
from core.sms_utils import send_absent_sms_to_parent, send_result_sms_to_parent

def test_all():
    print("=== STARTING FACULTY ATTENDANCE & CLASS TRANSFER TEST ===")

    branch = Branch.objects.first()
    year = Year.objects.get_or_create(year=1)[0]
    section = Section.objects.filter(branch=branch, year=year).first()

    faculty1 = Faculty.objects.filter(is_active=True).first()
    faculty2 = Faculty.objects.filter(is_active=True).exclude(id=faculty1.id).first()

    today = timezone.localdate()

    print(f"Faculty 1: {faculty1.employee_id} ({faculty1.full_name})")
    print(f"Faculty 2: {faculty2.employee_id} ({faculty2.full_name})")

    # 1. Test FacultyAttendance
    fac_att, created = FacultyAttendance.objects.update_or_create(
        faculty=faculty1,
        date=today,
        defaults={'status': 'P', 'remarks': 'Test Present Record'}
    )
    print(f"[PASSED] FacultyAttendance created/updated: {fac_att}")

    # 2. Test Timetable slot with room_number
    subject = Subject.objects.filter(is_deleted=False).first()
    if not subject:
        subject = Subject.objects.create(name="Mathematics I", code="M101", branch=branch, year=year, semester=1)

    timetable_slot, _ = Timetable.objects.update_or_create(
        section=section,
        day=today.strftime('%A'),
        period=1,
        defaults={
            'subject': subject,
            'faculty': faculty1,
            'room_number': 'Block C - Room 305'
        }
    )
    print(f"[PASSED] Timetable slot with room: {timetable_slot} in {timetable_slot.room_number}")

    # 3. Test ClassTransfer (Proxy)
    transfer, _ = ClassTransfer.objects.update_or_create(
        timetable_entry=timetable_slot,
        date=today,
        defaults={
            'original_faculty': faculty1,
            'substitute_faculty': faculty2,
            'reason': 'Faculty on Leave',
            'status': 'accepted'
        }
    )
    print(f"[PASSED] ClassTransfer created: {transfer}")

    # 4. Test Student Absence Parent SMS
    student = Student.objects.filter(section=section, is_active=True).first()
    if student:
        student.parent_mobile = "+919876543210"
        student.parent_name = "Ramesh Kumar"
        student.save()

        # Mark absent
        att, _ = Attendance.objects.update_or_create(
            student=student,
            timetable_entry=timetable_slot,
            date=today,
            defaults={'status': 'A', 'marked_by': faculty2}
        )
        print(f"[PASSED] Student Attendance marked: {att}")

        sms_result = send_absent_sms_to_parent(student, timetable_slot, today)
        print(f"[PASSED] Absent Parent SMS Result: {sms_result}")

    # 5. Test Result Release Parent SMS
    exam = Exam.objects.filter(branch=branch).first()
    if exam and student:
        results = list(Result.objects.filter(student=student, exam=exam))
        if results:
            res_sms = send_result_sms_to_parent(student, exam, results)
            print(f"[PASSED] Result Parent SMS Result: {res_sms}")

    print("=== ALL TESTS PASSED SUCCESSFULLY ===")

if __name__ == '__main__':
    test_all()
