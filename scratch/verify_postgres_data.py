import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.db import connection
from accounts.models import User, Student, Faculty
from core.models import Branch, Subject, Timetable, Result, Attendance, Notification

def verify():
    print("============================================================")
    print("  POSTGRESQL DATABASE VERIFICATION REPORT")
    print("============================================================")
    print(f"Database Engine : {connection.vendor.upper()} ({connection.settings_dict['ENGINE']})")
    print(f"Database Name   : {connection.settings_dict['NAME']}")
    print(f"Database Host   : {connection.settings_dict['HOST']}:{connection.settings_dict['PORT']}")
    print("------------------------------------------------------------")
    print(f"Total Users      : {User.objects.count()}")
    print(f"Total Students   : {Student.objects.count()}")
    print(f"Total Faculty    : {Faculty.objects.count()}")
    print(f"Total Branches   : {Branch.objects.count()}")
    print(f"Total Subjects   : {Subject.objects.count()}")
    print(f"Timetable Slots  : {Timetable.objects.count()}")
    print(f"Exam Results     : {Result.objects.count()}")
    print(f"Attendance Recs  : {Attendance.objects.count()}")
    print(f"Notifications    : {Notification.objects.count()}")
    print("============================================================")

if __name__ == '__main__':
    verify()
