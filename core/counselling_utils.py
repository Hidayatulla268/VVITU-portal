"""
VVIT Portal — Student Counselling Dossier & PDF Generation Utilities

Aggregates all student information across modules:
  • Demographic & Identity Details
  • Family, Parent & Residence Details
  • Fee Status & Dues
  • Semester-by-Semester Exam Marks, Grades & SGPA (R23 Regulation)
  • Cumulative CGPA & Credits Earned
  • Active Backlog Tracking
  • Semester-by-Semester Subject Attendance Records
  • Verified Co-Curricular & Extracurricular Achievements
  • Official ReportLab PDF Report Generation with Signatures
"""

import io
import datetime
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.conf import settings

from accounts.models import Student, Achievement, Faculty
from core.models import Subject, Exam, Result, Attendance, Timetable, Year, Branch


def get_student_counselling_dossier(student):
    """
    Compile a complete, structured dictionary of the student's academic,
    personal, family, attendance, and performance records across all semesters.
    """
    now = timezone.now()
    today = timezone.localdate()

    # 1. Demographic & Identity Data
    gender_val = student.gender or 'Not Specified'
    admission_year = student.admission_year or 2024
    branch_name = student.branch.name if student.branch else 'Unassigned'
    branch_code = student.branch.code if student.branch else 'GEN'
    year_num = student.year.year if student.year else 1
    section_name = student.section.name if student.section else 'Unassigned'

    # Current max semester based on year level (e.g. Year 2 -> Sem 4)
    max_active_sem = min(8, max(1, year_num * 2))

    class_teacher_name = student.class_teacher.full_name if student.class_teacher else 'Not Assigned'
    class_teacher_emp = student.class_teacher.employee_id if student.class_teacher else ''
    
    counsellor_name = student.counsellor.full_name if student.counsellor else 'Not Assigned'
    counsellor_emp = student.counsellor.employee_id if student.counsellor else ''
    counsellor_phone = student.counsellor.phone if student.counsellor else ''

    # 2. Family & Contact Details
    parent_name = student.parent_name or 'Not Provided'
    parent_occupation = student.parent_occupation or 'Not Provided'
    parent_mobile = student.parent_mobile or 'Not Provided'
    personal_mobile = student.personal_mobile or student.user.phone or 'Not Provided'
    email = student.user.email or 'Not Provided'
    permanent_address = student.permanent_address or 'Not Provided'
    present_address = student.present_address or student.permanent_address or 'Not Provided'
    caste = student.caste or 'General / OC'
    religion = student.religion or 'Not Specified'

    # 3. Fees Status
    fees_pending = float(student.fees_pending) if student.fees_pending is not None else 0.0
    fees_updated_at = student.fees_updated_at.strftime('%d-%b-%Y') if student.fees_updated_at else 'N/A'

    # 4. Semester-wise Exam Results, Marks, Grades & SGPA
    grade_points_map = {
        'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5,
        'F': 0, 'Ab': 0, 'CP': 0, 'NCP': 0
    }

    all_results = (
        Result.objects
        .filter(student=student)
        .select_related('exam', 'subject', 'subject__branch', 'subject__year')
    )

    # Check which semesters have subjects/results for this branch
    branch_subjects = (
        Subject.objects
        .filter(branch=student.branch, is_deleted=False)
        .order_by('semester', 'code')
    ) if student.branch else Subject.objects.none()

    # Determine all semesters to display (1 to max_active_sem, or any semester with records)
    semesters_with_data = set(all_results.values_list('exam__semester', flat=True))
    semesters_with_data.update(range(1, max_active_sem + 1))
    sorted_semesters = sorted([s for s in semesters_with_data if s and 1 <= s <= 8])
    if not sorted_semesters:
        sorted_semesters = [1]

    semester_reports = []
    total_cumulative_points = 0
    total_cumulative_credits = 0
    total_credits_earned = 0
    active_backlogs = []
    cleared_backlogs = []

    # Map of all attendance records for the student
    all_attendance = (
        Attendance.objects
        .filter(student=student)
        .select_related('timetable_entry__subject', 'timetable_entry__section')
    )

    for sem_num in sorted_semesters:
        # Subjects in this semester
        sem_subjects = list(branch_subjects.filter(semester=sem_num))
        
        # If no branch subjects registered for this semester, fall back to subjects present in results
        if not sem_subjects:
            res_sub_ids = all_results.filter(exam__semester=sem_num).values_list('subject_id', flat=True).distinct()
            sem_subjects = list(Subject.objects.filter(id__in=res_sub_ids))

        # Subject-wise marks & grades
        subj_rows = []
        sem_total_points = 0
        sem_total_credits = 0
        sem_credits_earned = 0
        has_sem_fail = False
        has_sem_results = False

        for subj in sem_subjects:
            s_results = all_results.filter(subject=subj, exam__semester=sem_num)
            mid1 = s_results.filter(exam__exam_type='mid1').first()
            mid2 = s_results.filter(exam__exam_type='mid2').first()
            final_res = s_results.filter(exam__exam_type='final').first()
            supply_res = s_results.filter(exam__exam_type='supply').order_by('-id').first()

            effective_final = supply_res if supply_res else final_res
            grade = effective_final.grade if (effective_final and effective_final.grade) else ''
            marks_obt = effective_final.marks_obtained if effective_final else None
            max_m = effective_final.max_marks if effective_final else None
            total_score = effective_final.final_total_score if effective_final else None

            credits = subj.credits if subj.credits is not None else 3
            pts = grade_points_map.get(grade, 0)
            is_pass = False

            if grade in ['S', 'A', 'B', 'C', 'D', 'E', 'CP']:
                is_pass = True
                sem_credits_earned += credits
                total_credits_earned += credits
            elif grade in ['F', 'Ab', 'NCP']:
                has_sem_fail = True
                active_backlogs.append({
                    'semester': sem_num,
                    'subject_code': subj.code,
                    'subject_name': subj.name,
                    'credits': credits,
                    'grade': grade or 'F'
                })

            if effective_final or mid1 or mid2:
                has_sem_results = True

            if grade and grade not in ['CP', 'NCP']:
                sem_total_points += (pts * credits)
                sem_total_credits += credits

            subj_rows.append({
                'subject': subj,
                'code': subj.code,
                'name': subj.name,
                'credits': credits,
                'mid1_marks': f"{float(mid1.marks_obtained):.1f}/{float(mid1.max_marks):.0f}" if mid1 else '—',
                'mid2_marks': f"{float(mid2.marks_obtained):.1f}/{float(mid2.max_marks):.0f}" if mid2 else '—',
                'final_marks': f"{float(marks_obt):.1f}/{float(max_m):.0f}" if marks_obt is not None else '—',
                'total_score': f"{float(total_score):.1f}" if total_score is not None else '—',
                'grade': grade if grade else '—',
                'grade_points': pts if grade else '—',
                'status': 'Pass' if is_pass else ('Fail' if grade in ['F', 'Ab', 'NCP'] else 'Pending')
            })

        sem_sgpa = round(sem_total_points / sem_total_credits, 2) if sem_total_credits > 0 else 0.0
        if sem_total_credits > 0:
            total_cumulative_points += sem_total_points
            total_cumulative_credits += sem_total_credits

        sem_status = '—'
        if has_sem_results:
            sem_status = 'Fail (Backlog)' if has_sem_fail else 'Pass'

        # 5. Semester Attendance Calculation
        sem_att_records = [
            r for r in all_attendance
            if r.timetable_entry and r.timetable_entry.subject and r.timetable_entry.subject.semester == sem_num
        ]
        
        sem_att_by_subj = {}
        for r in sem_att_records:
            scode = r.timetable_entry.subject.code
            sname = r.timetable_entry.subject.name
            if scode not in sem_att_by_subj:
                sem_att_by_subj[scode] = {'code': scode, 'name': sname, 'total': 0, 'present': 0}
            sem_att_by_subj[scode]['total'] += 1
            if r.status == 'P':
                sem_att_by_subj[scode]['present'] += 1

        sem_att_rows = []
        sem_total_classes = 0
        sem_present_classes = 0

        for scode, sinfo in sem_att_by_subj.items():
            t = sinfo['total']
            p = sinfo['present']
            pct = round(p / t * 100, 1) if t > 0 else 0.0
            sem_total_classes += t
            sem_present_classes += p
            sem_att_rows.append({
                'code': scode,
                'name': sinfo['name'],
                'total': t,
                'present': p,
                'absent': t - p,
                'percentage': pct,
            })

        sem_overall_att_pct = round(sem_present_classes / sem_total_classes * 100, 1) if sem_total_classes > 0 else 0.0

        semester_reports.append({
            'semester': sem_num,
            'subjects': subj_rows,
            'sgpa': sem_sgpa,
            'total_credits': sem_total_credits,
            'credits_earned': sem_credits_earned,
            'status': sem_status,
            'has_results': has_sem_results,
            'attendance_rows': sem_att_rows,
            'total_classes': sem_total_classes,
            'present_classes': sem_present_classes,
            'attendance_pct': sem_overall_att_pct,
        })

    # Overall Cumulative CGPA
    cgpa = round(total_cumulative_points / total_cumulative_credits, 2) if total_cumulative_credits > 0 else 0.0

    # Overall Total Attendance
    all_att_total = all_attendance.count()
    all_att_present = all_attendance.filter(status='P').count()
    overall_attendance_pct = round(all_att_present / all_att_total * 100, 1) if all_att_total > 0 else 0.0

    # 6. Achievements
    achievements_qs = Achievement.objects.filter(user=student.user).order_by('-date_achieved')
    achievements_list = list(achievements_qs)

    # 7. Student Photo / Profile Picture
    profile_pic_url = None
    profile_pic_path = None
    if hasattr(student, 'user') and student.user and student.user.profile_picture:
        try:
            profile_pic_url = student.user.profile_picture.url
            if hasattr(student.user.profile_picture, 'path') and os.path.exists(student.user.profile_picture.path):
                profile_pic_path = student.user.profile_picture.path
        except Exception:
            pass

    first_n = student.user.first_name if (hasattr(student, 'user') and student.user and student.user.first_name) else ''
    last_n = student.user.last_name if (hasattr(student, 'user') and student.user and student.user.last_name) else ''
    initials = f"{first_n[:1]}{last_n[:1]}".upper() or 'ST'

    return {
        'student': student,
        'roll_number': student.roll_number,
        'full_name': student.full_name or student.user.get_full_name(),
        'profile_picture_url': profile_pic_url,
        'profile_picture_path': profile_pic_path,
        'initials': initials,
        'email': email,
        'personal_mobile': personal_mobile,
        'gender': gender_val,
        'caste': caste,
        'religion': religion,
        'admission_year': admission_year,
        'branch_name': branch_name,
        'branch_code': branch_code,
        'year_num': year_num,
        'section_name': section_name,
        'class_teacher_name': class_teacher_name,
        'class_teacher_emp': class_teacher_emp,
        'counsellor_name': counsellor_name,
        'counsellor_emp': counsellor_emp,
        'counsellor_phone': counsellor_phone,
        'parent_name': parent_name,
        'parent_occupation': parent_occupation,
        'parent_mobile': parent_mobile,
        'permanent_address': permanent_address,
        'present_address': present_address,
        'fees_pending': fees_pending,
        'fees_updated_at': fees_updated_at,
        'semester_reports': semester_reports,
        'cgpa': cgpa,
        'total_cumulative_credits': total_cumulative_credits,
        'total_credits_earned': total_credits_earned,
        'active_backlogs': active_backlogs,
        'active_backlogs_count': len(active_backlogs),
        'overall_attendance_pct': overall_attendance_pct,
        'total_classes_conducted': all_att_total,
        'total_classes_attended': all_att_present,
        'achievements': achievements_list,
        'generated_at': now.strftime('%d %B %Y, %I:%M %p'),
        'today_date': today.strftime('%d-%b-%Y'),
    }


def generate_counselling_report_pdf(student):
    """
    Generate an official, beautifully-formatted multi-page PDF document
    for the student's counselling record using ReportLab.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    from reportlab.pdfgen import canvas

    dossier = get_student_counselling_dossier(student)
    buffer = io.BytesIO()

    # Numbered Canvas for "Page X of Y" and official watermark/footer
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_decorations(num_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_page_decorations(self, page_count):
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#475569"))

            # Top running line
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 805, 559, 805)
            self.drawString(36, 810, f"VVITU Student Dossier: {dossier['roll_number']} — {dossier['full_name']}")
            self.drawRightString(559, 810, "Official Counselling & Academic Record")

            # Bottom running line & footer
            self.line(36, 42, 559, 42)
            self.drawString(36, 30, "Vasireddy Venkatadri International Technological University • Confidential Student Record")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(559, 30, page_text)
            self.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'UnivTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#991B1B'),
        alignment=1
    )
    sub_title_style = ParagraphStyle(
        'UnivSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155'),
        alignment=1
    )
    badge_title_style = ParagraphStyle(
        'BadgeTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        alignment=1
    )
    section_head_style = ParagraphStyle(
        'SectionHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#991B1B'),
        spaceAfter=4
    )
    table_hdr_style = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=1
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A')
    )
    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=table_cell_style,
        alignment=1
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell_style,
        fontName='Helvetica-Bold'
    )
    small_muted_style = ParagraphStyle(
        'SmallMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#64748B')
    )

    elements = []

    # ── HEADER BANNER ─────────────────────────────────────────────────────────
    elements.append(Paragraph("VASIREDDY VENKATADRI INTERNATIONAL TECHNOLOGICAL UNIVERSITY", title_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("Approved by AICTE, Accredited by NAAC with 'A+' Grade • Recognized by UGC", sub_title_style))
    elements.append(Paragraph("Nambur (V), Pedakakani (M), Guntur District, Andhra Pradesh — 522508", sub_title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("STUDENT COUNSELLING & COMPREHENSIVE ACADEMIC DOSSIER", badge_title_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#991B1B"), spaceAfter=8))

    # ── STUDENT DEMOGRAPHICS & FAMILY PROFILE ─────────────────────────────────
    profile_data = [
        [
            Paragraph("<b>Roll Number:</b>", table_cell_style),
            Paragraph(f"<b>{dossier['roll_number']}</b>", table_cell_bold),
            Paragraph("<b>Full Name:</b>", table_cell_style),
            Paragraph(dossier['full_name'], table_cell_bold),
        ],
        [
            Paragraph("<b>Branch & Dept:</b>", table_cell_style),
            Paragraph(f"{dossier['branch_code']} ({dossier['branch_name']})", table_cell_style),
            Paragraph("<b>Year & Section:</b>", table_cell_style),
            Paragraph(f"Year {dossier['year_num']} — Sec {dossier['section_name']}", table_cell_style),
        ],
        [
            Paragraph("<b>Admission Year:</b>", table_cell_style),
            Paragraph(str(dossier['admission_year']), table_cell_style),
            Paragraph("<b>Gender / Caste:</b>", table_cell_style),
            Paragraph(f"{dossier['gender']} / {dossier['caste']}", table_cell_style),
        ],
        [
            Paragraph("<b>Student Mobile:</b>", table_cell_style),
            Paragraph(dossier['personal_mobile'], table_cell_style),
            Paragraph("<b>Email:</b>", table_cell_style),
            Paragraph(dossier['email'], table_cell_style),
        ],
        [
            Paragraph("<b>Parent Name:</b>", table_cell_style),
            Paragraph(dossier['parent_name'], table_cell_style),
            Paragraph("<b>Parent Occupation:</b>", table_cell_style),
            Paragraph(dossier['parent_occupation'], table_cell_style),
        ],
        [
            Paragraph("<b>Parent Contact:</b>", table_cell_style),
            Paragraph(dossier['parent_mobile'], table_cell_style),
            Paragraph("<b>Pending Fees:</b>", table_cell_style),
            Paragraph(f"INR {dossier['fees_pending']:,.2f}", table_cell_bold),
        ],
        [
            Paragraph("<b>Class Teacher:</b>", table_cell_style),
            Paragraph(f"{dossier['class_teacher_name']} ({dossier['class_teacher_emp']})", table_cell_style),
            Paragraph("<b>Assigned Counsellor:</b>", table_cell_style),
            Paragraph(f"{dossier['counsellor_name']} ({dossier['counsellor_emp']})", table_cell_style),
        ],
        [
            Paragraph("<b>Permanent Address:</b>", table_cell_style),
            Paragraph(dossier['permanent_address'], table_cell_style),
            Paragraph("<b>Present Address:</b>", table_cell_style),
            Paragraph(dossier['present_address'], table_cell_style),
        ]
    ]

    profile_details_table = Table(profile_data, colWidths=[78, 142, 84, 139])
    profile_details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.2),
    ]))

    # Student Photo in PDF
    from reportlab.platypus import Image as RLImage
    photo_cell = None
    if dossier.get('profile_picture_path') and os.path.exists(dossier['profile_picture_path']):
        try:
            photo_cell = RLImage(dossier['profile_picture_path'], width=68, height=84)
        except Exception:
            photo_cell = None

    if not photo_cell:
        photo_cell = [
            Spacer(1, 20),
            Paragraph(f"<font size=16 color='#991B1B'><b>{dossier['initials']}</b></font>", table_cell_center),
            Spacer(1, 12),
            Paragraph("<font size=6 color='#64748B'><b>STUDENT<br/>PHOTO</b></font>", table_cell_center)
        ]

    photo_box_table = Table([[photo_cell]], colWidths=[74])
    photo_box_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#94A3B8')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))

    combined_profile_table = Table([[photo_box_table, profile_details_table]], colWidths=[78, 445])
    combined_profile_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(combined_profile_table)
    elements.append(Spacer(1, 8))

    # ── ACADEMIC SUMMARY KPI BAR ──────────────────────────────────────────────
    kpi_data = [[
        Paragraph(f"<b>CUMULATIVE CGPA</b><br/><font size=11 color='#991B1B'><b>{dossier['cgpa']}</b></font>", table_cell_center),
        Paragraph(f"<b>TOTAL CREDITS EARNED</b><br/><font size=11 color='#047857'><b>{dossier['total_credits_earned']}</b> / {dossier['total_cumulative_credits']}</font>", table_cell_center),
        Paragraph(f"<b>ACTIVE BACKLOGS</b><br/><font size=11 color='#{ 'B91C1C' if dossier['active_backlogs_count'] > 0 else '047857' }'><b>{dossier['active_backlogs_count']}</b></font>", table_cell_center),
        Paragraph(f"<b>OVERALL ATTENDANCE</b><br/><font size=11 color='#0284C7'><b>{dossier['overall_attendance_pct']}%</b></font>", table_cell_center),
    ]]
    kpi_table = Table(kpi_data, colWidths=[130, 131, 131, 131])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#93C5FD')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BFDBFE')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 10))

    # ── SEMESTER-WISE MARKS & ATTENDANCE ──────────────────────────────────────
    for sem in dossier['semester_reports']:
        sem_elements = []
        sem_elements.append(Paragraph(
            f"<b>SEMESTER {sem['semester']} PERFORMANCE & ATTENDANCE RECORD</b> "
            f"— SGPA: <font color='#991B1B'><b>{sem['sgpa']}</b></font> | "
            f"Attendance: <font color='#0284C7'><b>{sem['attendance_pct']}%</b></font> | "
            f"Status: <b>{sem['status']}</b>",
            section_head_style
        ))

        # Academic Results Table
        table_rows = [[
            Paragraph("<b>Subject Code</b>", table_hdr_style),
            Paragraph("<b>Subject Name</b>", table_hdr_style),
            Paragraph("<b>Mid 1</b>", table_hdr_style),
            Paragraph("<b>Mid 2</b>", table_hdr_style),
            Paragraph("<b>Final</b>", table_hdr_style),
            Paragraph("<b>Total</b>", table_hdr_style),
            Paragraph("<b>Grade</b>", table_hdr_style),
            Paragraph("<b>Credits</b>", table_hdr_style),
            Paragraph("<b>Status</b>", table_hdr_style),
        ]]

        if sem['subjects']:
            for s in sem['subjects']:
                status_color = '#047857' if s['status'] == 'Pass' else ('#B91C1C' if s['status'] == 'Fail' else '#475569')
                table_rows.append([
                    Paragraph(s['code'], table_cell_center),
                    Paragraph(s['name'], table_cell_style),
                    Paragraph(str(s['mid1_marks']), table_cell_center),
                    Paragraph(str(s['mid2_marks']), table_cell_center),
                    Paragraph(str(s['final_marks']), table_cell_center),
                    Paragraph(str(s['total_score']), table_cell_center),
                    Paragraph(f"<b>{s['grade']}</b>", table_cell_center),
                    Paragraph(str(s['credits']), table_cell_center),
                    Paragraph(f"<font color='{status_color}'><b>{s['status']}</b></font>", table_cell_center),
                ])
        else:
            table_rows.append([
                Paragraph("—", table_cell_center),
                Paragraph("No examination subjects registered for this semester", table_cell_style),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
                Paragraph("—", table_cell_center),
            ])

        res_table = Table(table_rows, colWidths=[65, 178, 38, 38, 42, 40, 36, 40, 46])
        res_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#991B1B')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        sem_elements.append(res_table)
        sem_elements.append(Spacer(1, 4))

        # Attendance Breakdown for Semester
        if sem['attendance_rows']:
            att_header = [
                Paragraph("<b>Subject</b>", table_hdr_style),
                Paragraph("<b>Conducted</b>", table_hdr_style),
                Paragraph("<b>Attended</b>", table_hdr_style),
                Paragraph("<b>Absent</b>", table_hdr_style),
                Paragraph("<b>Attendance %</b>", table_hdr_style),
            ]
            att_table_rows = [att_header]
            for a in sem['attendance_rows']:
                att_pct_color = '#047857' if a['percentage'] >= 75 else ('#B45309' if a['percentage'] >= 65 else '#B91C1C')
                att_table_rows.append([
                    Paragraph(f"{a['code']} - {a['name']}", table_cell_style),
                    Paragraph(str(a['total']), table_cell_center),
                    Paragraph(str(a['present']), table_cell_center),
                    Paragraph(str(a['absent']), table_cell_center),
                    Paragraph(f"<font color='{att_pct_color}'><b>{a['percentage']}%</b></font>", table_cell_center),
                ])
            
            att_tbl = Table(att_table_rows, colWidths=[283, 60, 60, 60, 60])
            att_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
            ]))
            sem_elements.append(att_tbl)

        sem_elements.append(Spacer(1, 8))
        elements.append(KeepTogether(sem_elements))

    # ── CO-CURRICULAR & EXTRACURRICULAR ACHIEVEMENTS ──────────────────────────
    if dossier['achievements']:
        ach_elements = []
        ach_elements.append(Paragraph("<b>CO-CURRICULAR, CERTIFICATIONS & EXTRA-CURRICULAR ACHIEVEMENTS</b>", section_head_style))
        ach_table_rows = [[
            Paragraph("<b>Title / Event</b>", table_hdr_style),
            Paragraph("<b>Category</b>", table_hdr_style),
            Paragraph("<b>Date</b>", table_hdr_style),
            Paragraph("<b>Description / Achievement</b>", table_hdr_style),
        ]]
        for ach in dossier['achievements']:
            ach_table_rows.append([
                Paragraph(ach.title, table_cell_bold),
                Paragraph(ach.get_category_display() if hasattr(ach, 'get_category_display') else ach.category, table_cell_center),
                Paragraph(ach.date_achieved.strftime('%d-%b-%Y') if ach.date_achieved else '—', table_cell_center),
                Paragraph(ach.description or '—', table_cell_style),
            ])
        ach_table = Table(ach_table_rows, colWidths=[140, 95, 75, 213])
        ach_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        ach_elements.append(ach_table)
        ach_elements.append(Spacer(1, 10))
        elements.append(KeepTogether(ach_elements))

    # ── COUNSELLOR OBSERVATIONS & SIGNATURE BLOCKS ───────────────────────────
    sig_elements = []
    sig_elements.append(Paragraph("<b>COUNSELLING OBSERVATIONS & OFFICIAL ENDORSEMENT</b>", section_head_style))
    
    notes_box = [
        [Paragraph("<b>Counsellor Remarks & Periodic Observations:</b><br/><br/><br/>", table_cell_style)]
    ]
    notes_table = Table(notes_box, colWidths=[523])
    notes_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    sig_elements.append(notes_table)
    sig_elements.append(Spacer(1, 14))

    sig_data = [
        [
            Paragraph("________________________<br/><b>Student Signature</b><br/><font size=6 color='#64748B'>Date: ______________</font>", table_cell_center),
            Paragraph("________________________<br/><b>Faculty Counsellor</b><br/><font size=6 color='#64748B'>Prof. " + dossier['counsellor_name'] + "</font>", table_cell_center),
            Paragraph("________________________<br/><b>Head of Department (HOD)</b><br/><font size=6 color='#64748B'>Dept. of " + dossier['branch_code'] + "</font>", table_cell_center),
            Paragraph("________________________<br/><b>Principal / Dean</b><br/><font size=6 color='#64748B'>VVITU, Nambur</font>", table_cell_center),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[130, 131, 131, 131])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    sig_elements.append(sig_table)
    elements.append(KeepTogether(sig_elements))

    # Build PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
