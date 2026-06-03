import os
import sys
import django
import traceback

sys.path.append('c:/Users/HP/OneDrive/Desktop/vvit/vvit_portal_v8_THEME_CALENDAR/vvit_portal')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage
from student.views import results, dashboard
from accounts.models import Student

def add_middleware_to_request(request):
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

def test_student_views():
    students = Student.objects.all()
    print(f"Testing {students.count()} students...")
    
    success_count = 0
    failure_count = 0
    
    for s in students:
        print(f"\n--- Testing Student: {s.roll_number} (ID: {s.id}) ---")
        
        # Test dashboard
        req = RequestFactory().get('/student/dashboard/')
        req.user = s.user
        req.student = s
        add_middleware_to_request(req)
        try:
            res = dashboard(req)
            if res.status_code == 200:
                print("Dashboard: 200 OK")
            else:
                print(f"Dashboard returned status code: {res.status_code}")
        except Exception as e:
            print("Dashboard CRASHED:")
            traceback.print_exc()
            failure_count += 1
            continue
            
        # Test results for semester 1 to 8
        for sem in range(1, 9):
            req = RequestFactory().get(f'/student/results/?semester={sem}')
            req.user = s.user
            req.student = s
            add_middleware_to_request(req)
            try:
                res = results(req)
                if res.status_code == 200:
                    pass
                else:
                    print(f"Results Sem {sem} returned status code: {res.status_code}")
            except Exception as e:
                print(f"Results Sem {sem} CRASHED:")
                traceback.print_exc()
                failure_count += 1
                break
        else:
            print("Results Sem 1-8: All OK")
            success_count += 1
            
    print(f"\nSummary: {success_count} succeeded, {failure_count} failed.")

if __name__ == "__main__":
    test_student_views()
