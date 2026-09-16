"""
VVITU Portal — Secure Authorized Media Document Delivery
Serves private documents (leave certificates, feedback attachments) with role verification.
"""

import os
import mimetypes
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required


@login_required
def view_student_leave_document(request, leave_id):
    """
    Authorized document viewer for student leave/OD proofs.
    Access is strictly granted only to:
    1. The student who submitted the application.
    2. The student's assigned class teacher or counsellor.
    3. HOD of the student's department.
    4. Portal Administrators.
    """
    from accounts.models import StudentLeaveRequest, Student, Faculty

    leave_req = get_object_or_404(StudentLeaveRequest, id=leave_id)
    if not leave_req.document:
        raise Http404("No document attached to this leave request.")

    user = request.user
    can_view = False

    if user.is_staff or user.role == 'admin':
        can_view = True
    elif user.role == 'student' and hasattr(user, 'student_profile'):
        if leave_req.student == user.student_profile:
            can_view = True
    elif user.role in ['faculty', 'hod', 'lab_technician'] and hasattr(user, 'faculty_profile'):
        faculty = user.faculty_profile
        student = leave_req.student
        if student.class_teacher == faculty or student.counsellor == faculty:
            can_view = True
        elif user.role == 'hod' and student.branch == faculty.department:
            can_view = True

    if not can_view:
        return HttpResponseForbidden("Access Denied: You do not have permission to inspect this confidential student leave document.")

    try:
        file_handle = leave_req.document.open('rb')
    except Exception:
        raise Http404("Document file could not be retrieved from storage.")

    content_type, _ = mimetypes.guess_type(leave_req.document.name)
    content_type = content_type or 'application/octet-stream'

    response = FileResponse(file_handle, content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(leave_req.document.name)}"'
    return response


@login_required
def view_feedback_document(request, form_id):
    """
    Authorized document viewer for feedback questionnaire forms.
    Access is granted to:
    1. Admin / HOD / Faculty.
    2. Students whose Branch, Year, and Section match the form's target scope.
    """
    from core.models import FeedbackForm

    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    if not form_obj.uploaded_document:
        raise Http404("No document attached to this feedback form.")

    user = request.user
    can_view = False

    if user.is_staff or user.role in ['admin', 'hod', 'faculty', 'deo']:
        can_view = True
    elif user.role == 'student' and hasattr(user, 'student_profile'):
        student = user.student_profile
        # Check scope match
        branch_match = (form_obj.branch is None or form_obj.branch == student.branch)
        year_match = (form_obj.year is None or form_obj.year == student.year)
        sec_match = (form_obj.section is None or form_obj.section == student.section)
        if branch_match and year_match and sec_match and form_obj.is_active:
            can_view = True

    if not can_view:
        return HttpResponseForbidden("Access Denied: You do not have permission to view this feedback questionnaire document.")

    try:
        file_handle = form_obj.uploaded_document.open('rb')
    except Exception:
        raise Http404("Document file could not be retrieved from storage.")

    content_type, _ = mimetypes.guess_type(form_obj.uploaded_document.name)
    content_type = content_type or 'application/octet-stream'

    response = FileResponse(file_handle, content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(form_obj.uploaded_document.name)}"'
    return response
