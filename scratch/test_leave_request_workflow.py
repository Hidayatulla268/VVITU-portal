import os
import sys
import datetime
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from accounts.models import User, Faculty, FacultyLeaveRequest
from core.models import Notification

def test_leave_workflow():
    print("============================================================")
    print("  TESTING FACULTY LEAVE REQUEST & APPROVAL WORKFLOW")
    print("============================================================")

    # 1. Pick a faculty member
    faculty = Faculty.objects.first()
    if not faculty:
        print("No faculty members found!")
        return

    print(f"Faculty Member : {faculty.full_name} ({faculty.employee_id})")
    print(f"Department     : {faculty.department}")

    # 2. Create Leave Request
    today = datetime.date.today()
    start_date = today + datetime.timedelta(days=2)
    end_date = today + datetime.timedelta(days=4)

    leave_req = FacultyLeaveRequest.objects.create(
        faculty=faculty,
        leave_type='casual',
        start_date=start_date,
        end_date=end_date,
        reason="Attending National Technological Conference",
        substitute_notes="Periods substituted by CSE Faculty",
        status='pending'
    )
    print(f"\n[CREATED LEAVE REQUEST]")
    print(f"ID         : {leave_req.id}")
    print(f"Type       : {leave_req.get_leave_type_display()}")
    print(f"Duration   : {leave_req.start_date} to {leave_req.end_date} ({leave_req.total_days} Days)")
    print(f"Status     : {leave_req.status}")

    # 3. Simulate HOD / Admin Approval
    hod_user = User.objects.filter(role='hod').first() or User.objects.filter(role='admin').first()
    print(f"\n[ACTION BY HOD/ADMIN: {hod_user.get_full_name() or hod_user.username}]")

    leave_req.status = 'approved'
    leave_req.action_by = hod_user
    leave_req.action_at = datetime.datetime.now()
    leave_req.admin_remarks = "Approved by HOD. Have a good conference."
    leave_req.save()

    print(f"Updated Status : {leave_req.status.upper()}")
    print(f"Actioned By    : {leave_req.action_by.get_full_name()} ({leave_req.action_by.role})")
    print(f"Remarks        : {leave_req.admin_remarks}")

    # Clean up test leave request
    leave_req.delete()
    print("\n[SUCCESS] Leave request workflow test completed successfully!")
    print("============================================================")

if __name__ == '__main__':
    test_leave_workflow()
