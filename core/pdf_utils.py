"""
VVITU Portal — Official ReportLab PDF Generation Utilities

Generates institutional-grade PDF documents:
1. Monthly Subject Attendance Matrix (Landscape A4)
2. Official Semester Grade Card & Transcript (Portrait A4)
3. HOD Detention & Condonation Official Roll (Portrait/Landscape A4)
"""

import io
import datetime
import calendar
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds running confidential header, footer, and page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Footer
        footer_text = f"VVITU Academic Management System · Generated on {datetime.datetime.now().strftime('%d-%b-%Y %H:%M')}"
        page_text = f"Page {self._pageNumber} of {page_count}"
        
        # Check orientation
        width, height = self._pagesize
        self.drawString(36, 20, footer_text)
        self.drawRightString(width - 36, 20, page_text)
        
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 30, width - 36, 30)
        self.restoreState()


def generate_monthly_attendance_pdf(student, selected_month, selected_cal_year, selected_sem=None):
    """
    Generates a print-ready Landscape A4 Monthly Subject Attendance Statement.
    """
    from core.models import Attendance, Subject
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.HexColor('#0f172a'))
    sub_style = ParagraphStyle('Sub', fontName='Helvetica', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#475569'))
    header_style = ParagraphStyle('Hdr', fontName='Helvetica-Bold', fontSize=10, leading=13, alignment=1, textColor=colors.HexColor('#1e293b'))
    cell_style = ParagraphStyle('Cell', fontName='Helvetica', fontSize=7.5, leading=9, alignment=0, textColor=colors.HexColor('#1e293b'))
    p_style = ParagraphStyle('P', fontName='Helvetica-Bold', fontSize=7.5, leading=8, alignment=1, textColor=colors.HexColor('#059669'))
    a_style = ParagraphStyle('A', fontName='Helvetica-Bold', fontSize=7.5, leading=8, alignment=1, textColor=colors.HexColor('#dc2626'))
    l_style = ParagraphStyle('L', fontName='Helvetica-Bold', fontSize=7.5, leading=8, alignment=1, textColor=colors.HexColor('#d97706'))
    h_style = ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=7.5, leading=8, alignment=1, textColor=colors.HexColor('#7c3aed'))
    stat_style = ParagraphStyle('Stat', fontName='Helvetica-Bold', fontSize=8, leading=9, alignment=1, textColor=colors.HexColor('#0f172a'))

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("<b>VASIREDDY VENKATADRI INSTITUTE OF TECHNOLOGY</b>", title_style))
    elements.append(Paragraph("Autonomous Institution &middot; Approved by AICTE &middot; Accredited by NAAC 'A' Grade & NBA", sub_style))
    elements.append(Spacer(1, 4))
    m_name = calendar.month_name[selected_month]
    elements.append(Paragraph(f"<b>MONTHLY SUBJECT ATTENDANCE STATEMENT &middot; {m_name.upper()} {selected_cal_year}</b>", header_style))
    elements.append(Spacer(1, 8))

    # 2. Student Info Box
    student_info = [
        [
            Paragraph(f"<b>Roll No:</b> {student.roll_number}", cell_style),
            Paragraph(f"<b>Student Name:</b> {student.user.get_full_name()}", cell_style),
            Paragraph(f"<b>Branch:</b> {student.branch.code if student.branch else '—'}", cell_style),
            Paragraph(f"<b>Year/Sec:</b> {student.year if student.year else '—'} / Sec {student.section.name if student.section else '—'}", cell_style),
        ]
    ]
    info_table = Table(student_info, colWidths=[150, 240, 180, 170])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # 3. Monthly Matrix Computations
    _, num_days = calendar.monthrange(selected_cal_year, selected_month)
    start_d = datetime.date(selected_cal_year, selected_month, 1)
    end_d = datetime.date(selected_cal_year, selected_month, num_days)

    records = Attendance.objects.filter(
        student=student,
        date__range=(start_d, end_d)
    ).select_related('timetable_entry__subject', 'timetable_entry__faculty__user')

    if selected_sem:
        records = records.filter(timetable_entry__subject__semester=selected_sem)

    # Group records by subject
    subjects_dict = {}
    for r in records:
        s = r.timetable_entry.subject
        if s.id not in subjects_dict:
            subjects_dict[s.id] = {
                'code': s.code,
                'name': s.name,
                'records': []
            }
        subjects_dict[s.id]['records'].append(r)

    # Headers: Subject + Days 01..num_days + P, A, L, H, %
    day_headers = [f"{d:02d}" for d in range(1, num_days + 1)]
    table_header = [Paragraph("<b>SUBJECT</b>", ParagraphStyle('Th', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=0))]
    for dh in day_headers:
        table_header.append(Paragraph(f"<b>{dh}</b>", ParagraphStyle('ThD', fontName='Helvetica-Bold', fontSize=6.5, textColor=colors.white, alignment=1)))
    table_header.extend([
        Paragraph("<b>P</b>", ParagraphStyle('ThS', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1)),
        Paragraph("<b>A</b>", ParagraphStyle('ThS', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1)),
        Paragraph("<b>L</b>", ParagraphStyle('ThS', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1)),
        Paragraph("<b>H</b>", ParagraphStyle('ThS', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1)),
        Paragraph("<b>%</b>", ParagraphStyle('ThS', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1)),
    ])

    table_data = [table_header]

    total_month_p = 0
    total_month_a = 0
    total_month_l = 0
    total_month_h = 0

    for sid in sorted(subjects_dict.keys()):
        sdata = subjects_dict[sid]
        s_recs = sdata['records']
        p_cnt = sum(1 for r in s_recs if r.status == 'P')
        a_cnt = sum(1 for r in s_recs if r.status == 'A')
        l_cnt = sum(1 for r in s_recs if r.status == 'L')
        h_cnt = sum(1 for r in s_recs if r.status == 'H')
        
        total_month_p += p_cnt
        total_month_a += a_cnt
        total_month_l += l_cnt
        total_month_h += h_cnt

        held = p_cnt + a_cnt
        pct_str = f"{round(p_cnt / held * 100, 1)}%" if held > 0 else "100.0%"

        row = [Paragraph(f"<b>{sdata['code']}</b> - {sdata['name'][:22]}", cell_style)]
        for d in range(1, num_days + 1):
            d_date = datetime.date(selected_cal_year, selected_month, d)
            d_recs = [r for r in s_recs if r.date == d_date]
            if not d_recs:
                row.append(Paragraph("", cell_style))
            else:
                has_a = any(r.status == 'A' for r in d_recs)
                has_p = any(r.status == 'P' for r in d_recs)
                has_l = any(r.status == 'L' for r in d_recs)
                has_h = any(r.status == 'H' for r in d_recs)
                if has_a and not has_p:
                    row.append(Paragraph("A", a_style))
                elif has_p:
                    row.append(Paragraph("P", p_style))
                elif has_l:
                    row.append(Paragraph("L", l_style))
                elif has_h:
                    row.append(Paragraph("H", h_style))
                else:
                    row.append(Paragraph("P", p_style))

        row.extend([
            Paragraph(str(p_cnt), stat_style),
            Paragraph(str(a_cnt), stat_style),
            Paragraph(str(l_cnt), stat_style),
            Paragraph(str(h_cnt), stat_style),
            Paragraph(pct_str, stat_style),
        ])
        table_data.append(row)

    # Total Summary Row
    tot_held = total_month_p + total_month_a
    overall_pct_str = f"{round(total_month_p / tot_held * 100, 1)}%" if tot_held > 0 else "—"
    
    total_row = [Paragraph("<b>TOTAL MONTHLY SUMMARY</b>", ParagraphStyle('Tot', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.HexColor('#dc2626')))]
    for _ in range(num_days):
        total_row.append(Paragraph("", cell_style))
    total_row.extend([
        Paragraph(f"<b>{total_month_p}</b>", ParagraphStyle('TotP', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#059669'), alignment=1)),
        Paragraph(f"<b>{total_month_a}</b>", ParagraphStyle('TotA', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#dc2626'), alignment=1)),
        Paragraph(f"<b>{total_month_l}</b>", stat_style),
        Paragraph(f"<b>{total_month_h}</b>", stat_style),
        Paragraph(f"<b>{overall_pct_str}</b>", ParagraphStyle('TotPct', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0f172a'), alignment=1)),
    ])
    table_data.append(total_row)

    # Calculate column widths
    # Available width ~ 790 points
    subject_w = 175
    stat_w = 20
    pct_w = 35
    days_total_w = 790 - subject_w - (stat_w * 4) - pct_w
    day_w = max(16, days_total_w / num_days)

    col_widths = [subject_w] + [day_w] * num_days + [stat_w, stat_w, stat_w, stat_w, pct_w]

    matrix_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor('#dc2626')),
    ]))
    elements.append(matrix_table)
    elements.append(Spacer(1, 20))

    # 4. Official Signature Blocks
    sig_data = [
        [
            Paragraph("<b>Class Incharge / Counsellor</b><br/><br/><br/>Signature with Date", sub_style),
            Paragraph("<b>Head of Department (HOD)</b><br/><br/><br/>Signature with Date", sub_style),
            Paragraph("<b>Controller of Examinations / Principal</b><br/><br/><br/>Signature with Seal", sub_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[240, 260, 240])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(KeepTogether(sig_table))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generate_semester_grade_card_pdf(student, selected_sem=None):
    """
    Generates an official Portrait A4 Semester Grade Card Transcript.
    """
    from core.models import Result, Subject
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=15, leading=18, alignment=1, textColor=colors.HexColor('#0f172a'))
    sub_style = ParagraphStyle('Sub', fontName='Helvetica', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#475569'))
    hdr_style = ParagraphStyle('Hdr', fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#dc2626'))
    cell_style = ParagraphStyle('Cell', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#1e293b'))
    th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, leading=10, textColor=colors.white, alignment=1)
    bold_style = ParagraphStyle('Bld', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor('#0f172a'))

    elements = []

    # 1. Header
    elements.append(Paragraph("<b>VASIREDDY VENKATADRI INSTITUTE OF TECHNOLOGY</b>", title_style))
    elements.append(Paragraph("Autonomous Institution &middot; Approved by AICTE &middot; Accredited by NAAC 'A' Grade & NBA", sub_style))
    elements.append(Paragraph("Guntur, Andhra Pradesh — 522508", sub_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>OFFICIAL SEMESTER GRADE REPORT & TRANSCRIPT</b>", hdr_style))
    elements.append(Spacer(1, 12))

    # 2. Student Info Card
    sem_text = f"Semester {selected_sem}" if selected_sem else "Cumulative Records"
    student_info = [
        [
            Paragraph(f"<b>Roll Number:</b> {student.roll_number}", cell_style),
            Paragraph(f"<b>Academic Regulation:</b> R23", cell_style),
        ],
        [
            Paragraph(f"<b>Student Name:</b> {student.user.get_full_name()}", cell_style),
            Paragraph(f"<b>Academic Semester:</b> {sem_text}", cell_style),
        ],
        [
            Paragraph(f"<b>Branch / Course:</b> {student.branch.name if student.branch else '—'}", cell_style),
            Paragraph(f"<b>Batch:</b> {student.admission_year} - {student.admission_year + 4}", cell_style),
        ]
    ]
    info_table = Table(student_info, colWidths=[260, 260])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 14))

    # 3. Results Table
    results = Result.objects.filter(
        student=student,
        exam__release__released=True
    ).select_related('subject', 'exam').order_by('subject__semester', 'subject__code')

    if selected_sem:
        results = results.filter(subject__semester=selected_sem)

    table_data = [
        [
            Paragraph("<b>Code</b>", th_style),
            Paragraph("<b>Subject Title</b>", ParagraphStyle('ThL', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.white)),
            Paragraph("<b>Sem</b>", th_style),
            Paragraph("<b>Credits</b>", th_style),
            Paragraph("<b>Grade</b>", th_style),
            Paragraph("<b>Points</b>", th_style),
            Paragraph("<b>Status</b>", th_style),
        ]
    ]

    grade_points_map = {'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5, 'F': 0, 'Ab': 0}
    total_credits = 0
    total_earned_credits = 0
    total_points_earned = 0

    for r in results:
        sub = r.subject
        cred = getattr(sub, 'credits', 3) or 3
        grade = r.grade or '—'
        pts = grade_points_map.get(grade, 0)
        is_pass = grade not in ['F', 'Ab', '—']

        total_credits += cred
        if is_pass:
            total_earned_credits += cred
            total_points_earned += (pts * cred)

        status_text = "PASS" if is_pass else "FAIL"
        status_color = colors.HexColor('#059669') if is_pass else colors.HexColor('#dc2626')

        table_data.append([
            Paragraph(sub.code, cell_style),
            Paragraph(sub.name, cell_style),
            Paragraph(str(sub.semester), bold_style),
            Paragraph(str(cred), bold_style),
            Paragraph(f"<b>{grade}</b>", bold_style),
            Paragraph(str(pts), bold_style),
            Paragraph(f"<b>{status_text}</b>", ParagraphStyle('St', fontName='Helvetica-Bold', fontSize=8.5, textColor=status_color, alignment=1)),
        ])

    sgpa = round(total_points_earned / total_credits, 2) if total_credits > 0 else 0.0

    res_table = Table(table_data, colWidths=[65, 205, 40, 50, 45, 45, 70], repeatRows=1)
    res_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(res_table)
    elements.append(Spacer(1, 12))

    # 4. Summary & Performance Indicator
    summary_data = [
        [
            Paragraph(f"<b>Total Registered Credits:</b> {total_credits}", cell_style),
            Paragraph(f"<b>Earned Credits:</b> {total_earned_credits}", cell_style),
            Paragraph(f"<b>Semester GPA (SGPA):</b> <font color='#059669'><b>{sgpa}</b></font>", ParagraphStyle('SGPA', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#059669'))),
        ]
    ]
    sum_table = Table(summary_data, colWidths=[175, 175, 170])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(sum_table)
    elements.append(Spacer(1, 30))

    # 5. Signatures
    sig_data = [
        [
            Paragraph("<b>Prepared By</b><br/><br/><br/>Verification Officer", sub_style),
            Paragraph("<b>Head of the Department</b><br/><br/><br/>Signature with Seal", sub_style),
            Paragraph("<b>Controller of Examinations</b><br/><br/><br/>Official Signature & Seal", sub_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[170, 180, 170])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(KeepTogether(sig_table))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# 4. STUDENT FEEDBACK SUMMARY & ACKNOWLEDGMENT PDF
# ─────────────────────────────────────────────
def generate_student_feedback_summary_pdf(submission):
    """
    Generates an official Portrait A4 PDF summary and acknowledgment receipt
    for a student's completed feedback submission.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1, textColor=colors.HexColor('#800000'))
    sub_style    = ParagraphStyle('Sub',   fontName='Helvetica', fontSize=8, leading=11, alignment=1, textColor=colors.HexColor('#475569'))
    banner_style = ParagraphStyle('Bnr',   fontName='Helvetica-Bold', fontSize=10.5, leading=13, alignment=1, textColor=colors.HexColor('#1e293b'))
    cell_style   = ParagraphStyle('Cell',  fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor('#1e293b'))
    bold_style   = ParagraphStyle('Bold',  fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.HexColor('#0f172a'))
    center_bold  = ParagraphStyle('CBold', fontName='Helvetica-Bold', fontSize=8, leading=10.5, alignment=1, textColor=colors.HexColor('#0f172a'))
    hdr_style    = ParagraphStyle('Hdr',   fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.white)
    rating_style = ParagraphStyle('Rate',  fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, alignment=1, textColor=colors.HexColor('#800000'))
    remarks_style= ParagraphStyle('Rem',   fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#334155'))

    elements = []
    student = submission.student
    form = submission.form

    # 1. Header Banner
    elements.append(Paragraph("<b>VASIREDDY VENKATADRI INSTITUTE OF TECHNOLOGY</b>", title_style))
    elements.append(Paragraph("Autonomous Institution &middot; Approved by AICTE &middot; Permanently Affiliated to JNTUK &middot; Accredited by NAAC with 'A' Grade", sub_style))
    elements.append(Paragraph("Nambur (V), Peda Kakani (M), Guntur &ndash; 522 508, Andhra Pradesh", sub_style))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#800000'), spaceAfter=6))
    elements.append(Paragraph(f"<b>STUDENT FEEDBACK SUBMISSION SUMMARY &middot; ACKNOWLEDGMENT</b>", banner_style))
    elements.append(Paragraph(f"<font color='#64748b'>Form: <b>{form.title}</b> &middot; {form.get_feedback_type_display()}</font>", sub_style))
    elements.append(Spacer(1, 10))

    # 2. Student & Submission Info Grid
    branch_name = student.branch.name if student.branch else "N/A"
    branch_code = student.branch.code if student.branch else "N/A"
    sec_name    = student.section.name if student.section else "-"
    year_val    = student.year.get_year_display() if student.year else "-"

    info_data = [
        [
            Paragraph(f"<b>Student Name:</b> {student.user.get_full_name()}", cell_style),
            Paragraph(f"<b>Reference No:</b> <font color='#800000'><b>{submission.reference_no}</b></font>", cell_style),
        ],
        [
            Paragraph(f"<b>Roll Number:</b> <b>{student.roll_number}</b>", cell_style),
            Paragraph(f"<b>Submission Date:</b> {submission.submitted_at.strftime('%d-%b-%Y %I:%M %p')}", cell_style),
        ],
        [
            Paragraph(f"<b>Program / Dept:</b> {branch_code} ({branch_name})", cell_style),
            Paragraph(f"<b>Submission Mode:</b> {submission.get_submission_mode_display()}", cell_style),
        ],
        [
            Paragraph(f"<b>Year & Section:</b> {year_val} &middot; Section {sec_name}", cell_style),
            Paragraph(f"<b>Overall Rating Given:</b> <b>{submission.average_rating} / 5.0</b>", cell_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[260, 263])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # 3. Questions & Responses Table
    answers = submission.answers.select_related('question').order_by('question__order', 'id')
    
    table_data = [
        [
            Paragraph("<b>S.No</b>", hdr_style),
            Paragraph("<b>Evaluation Parameter / Question</b>", ParagraphStyle('HdrL', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=0, textColor=colors.white)),
            Paragraph("<b>Response / Score</b>", hdr_style),
        ]
    ]

    rating_labels = {
        5: "5 - Excellent ★★★★★",
        4: "4 - Very Good ★★★★☆",
        3: "3 - Good ★★★☆☆",
        2: "2 - Fair ★★☆☆☆",
        1: "1 - Poor ★☆☆☆☆",
    }

    for idx, ans in enumerate(answers, 1):
        q = ans.question
        if ans.rating_value is not None:
            ans_display = rating_labels.get(ans.rating_value, f"{ans.rating_value} Stars")
            ans_para = Paragraph(f"<b>{ans_display}</b>", rating_style)
        elif ans.choice_value:
            ans_para = Paragraph(f"<b>{ans.choice_value}</b>", bold_style)
        elif ans.text_value:
            ans_para = Paragraph(f"{ans.text_value}", remarks_style)
        else:
            ans_para = Paragraph("<font color='#94a3b8'>No response</font>", cell_style)

        table_data.append([
            Paragraph(str(idx), center_bold),
            Paragraph(f"<b>{q.question_text}</b>", cell_style),
            ans_para,
        ])

    q_table = Table(table_data, colWidths=[35, 335, 153], repeatRows=1)
    q_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#800000')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fbfcfd')]),
    ]))
    elements.append(q_table)
    elements.append(Spacer(1, 10))

    # 4. Overall Comments Box
    if submission.overall_comments:
        comments_data = [
            [
                Paragraph("<b>Student's General Remarks & Suggestions:</b><br/>" + submission.overall_comments.replace('\n', '<br/>'), remarks_style)
            ]
        ]
        comm_table = Table(comments_data, colWidths=[523])
        comm_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(comm_table)
        elements.append(Spacer(1, 14))

    # 5. Digital Verification Seal & Signatures
    verif_data = [
        [
            Paragraph("<font size=7 color='#64748b'><b>SYSTEM GENERATED ACKNOWLEDGMENT</b><br/>This document confirms the online submission of academic feedback on the VVITU Portal. Recorded under digital integrity verification.</font>", cell_style),
            Paragraph("<b>Student Signature</b><br/><br/><br/>(Digitally Verified via Roll Auth)", ParagraphStyle('SSig', fontName='Helvetica', fontSize=7.5, leading=10, alignment=1, textColor=colors.HexColor('#475569'))),
            Paragraph("<b>Head of Department</b><br/><br/><br/>Department of " + (branch_code or "Academic Unit"), ParagraphStyle('HSig', fontName='Helvetica', fontSize=7.5, leading=10, alignment=1, textColor=colors.HexColor('#475569'))),
        ]
    ]
    verif_table = Table(verif_data, colWidths=[240, 140, 143])
    verif_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (1,0), (2,0), 'CENTER'),
    ]))
    elements.append(KeepTogether(verif_table))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# 5. BLANK PRINTABLE FEEDBACK FORM PDF (OFFLINE)
# ─────────────────────────────────────────────
def generate_feedback_blank_printable_pdf(feedback_form):
    """
    Generates an official printable blank feedback form in Portrait A4
    for physical distribution, manual filling, and offline submission.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1, textColor=colors.HexColor('#800000'))
    sub_style    = ParagraphStyle('Sub',   fontName='Helvetica', fontSize=8, leading=11, alignment=1, textColor=colors.HexColor('#475569'))
    banner_style = ParagraphStyle('Bnr',   fontName='Helvetica-Bold', fontSize=10, leading=13, alignment=1, textColor=colors.HexColor('#1e293b'))
    cell_style   = ParagraphStyle('Cell',  fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor('#1e293b'))
    center_bold  = ParagraphStyle('CBold', fontName='Helvetica-Bold', fontSize=8, leading=10.5, alignment=1, textColor=colors.HexColor('#0f172a'))
    hdr_style    = ParagraphStyle('Hdr',   fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1, textColor=colors.white)

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("<b>VASIREDDY VENKATADRI INSTITUTE OF TECHNOLOGY</b>", title_style))
    elements.append(Paragraph("Autonomous Institution &middot; Approved by AICTE &middot; Permanently Affiliated to JNTUK &middot; Accredited by NAAC 'A' Grade", sub_style))
    elements.append(Paragraph("Nambur, Guntur &ndash; 522 508, Andhra Pradesh", sub_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#800000'), spaceAfter=5))
    elements.append(Paragraph(f"<b>STUDENT EVALUATION & FEEDBACK QUESTIONNAIRE &middot; PHYSICAL FORM</b>", banner_style))
    elements.append(Paragraph(f"<b>Form Title:</b> {feedback_form.title} &middot; <font color='#64748b'>{feedback_form.get_feedback_type_display()} ({feedback_form.target_display})</font>", sub_style))
    elements.append(Spacer(1, 8))

    # 2. Blank Student Identification Block
    blank_info_data = [
        [
            Paragraph("<b>Student Name:</b> ____________________________________", cell_style),
            Paragraph("<b>Roll Number:</b> ________________________", cell_style),
        ],
        [
            Paragraph("<b>Department & Year:</b> ______________________________", cell_style),
            Paragraph("<b>Section:</b> _____ &nbsp;&nbsp; <b>Date:</b> _____________", cell_style),
        ],
    ]
    blank_table = Table(blank_info_data, colWidths=[280, 243])
    blank_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(blank_table)
    elements.append(Spacer(1, 8))

    # 3. Rating Scale Legend / Instructions
    questions = feedback_form.questions.all().order_by('order', 'id')
    is_choice_form = all(q.question_type == 'choice' for q in questions) if questions.exists() else False
    
    if is_choice_form:
        legend_data = [
            [
                Paragraph("<b>Offline Instructions:</b> &nbsp; Please mark [ <b>&times;</b> ] or [ <b>&check;</b> ] in the respective choice column and write remarks/comments if applicable.", ParagraphStyle('Leg', fontName='Helvetica', fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor('#334155')))
            ]
        ]
    else:
        legend_data = [
            [
                Paragraph("<b>Evaluation Rating Scale:</b> &nbsp; <b>5</b> = Excellent &nbsp;|&nbsp; <b>4</b> = Very Good &nbsp;|&nbsp; <b>3</b> = Good &nbsp;|&nbsp; <b>2</b> = Fair &nbsp;|&nbsp; <b>1</b> = Poor", ParagraphStyle('Leg', fontName='Helvetica', fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor('#334155')))
            ]
        ]
    leg_table = Table(legend_data, colWidths=[523])
    leg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(leg_table)
    elements.append(Spacer(1, 8))

    # 4. Questionnaire Grid
    if is_choice_form:
        grid_data = [
            [
                Paragraph("<b>S.No</b>", hdr_style),
                Paragraph("<b>Evaluation Parameter / Question</b>", ParagraphStyle('HdrL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=0, textColor=colors.white)),
                Paragraph("<b>Yes</b>", hdr_style),
                Paragraph("<b>No</b>", hdr_style),
                Paragraph("<b>Remarks, if any</b>", hdr_style),
            ]
        ]
        for idx, q in enumerate(questions, 1):
            grid_data.append([
                Paragraph(str(idx), center_bold),
                Paragraph(f"{q.question_text}", cell_style),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("____________________", ParagraphStyle('RmkB', fontName='Helvetica', fontSize=7, leading=8, textColor=colors.HexColor('#94a3b8'))),
            ])
        q_grid = Table(grid_data, colWidths=[28, 335, 35, 35, 90], repeatRows=1)
    else:
        grid_data = [
            [
                Paragraph("<b>S.No</b>", hdr_style),
                Paragraph("<b>Evaluation Parameter / Question</b>", ParagraphStyle('HdrL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=0, textColor=colors.white)),
                Paragraph("<b>5</b>", hdr_style),
                Paragraph("<b>4</b>", hdr_style),
                Paragraph("<b>3</b>", hdr_style),
                Paragraph("<b>2</b>", hdr_style),
                Paragraph("<b>1</b>", hdr_style),
                Paragraph("<b>Remarks</b>", hdr_style),
            ]
        ]
        for idx, q in enumerate(questions, 1):
            grid_data.append([
                Paragraph(str(idx), center_bold),
                Paragraph(f"{q.question_text}", cell_style),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("[ &nbsp; ]", center_bold),
                Paragraph("________________", ParagraphStyle('RmkB', fontName='Helvetica', fontSize=7, leading=8, textColor=colors.HexColor('#94a3b8'))),
            ])
        q_grid = Table(grid_data, colWidths=[28, 275, 28, 28, 28, 28, 28, 80], repeatRows=1)
    q_grid.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#800000')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (2,1), (6,-1), 'CENTER'),
    ]))
    elements.append(q_grid)
    elements.append(Spacer(1, 8))

    # 5. Suggestions & Signature block
    footer_data = [
        [
            Paragraph("<b>Suggestions / General Comments:</b><br/><br/>____________________________________________________________________________________________________________<br/><br/>____________________________________________________________________________________________________________", cell_style)
        ]
    ]
    f_table = Table(footer_data, colWidths=[523])
    f_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(f_table)
    elements.append(Spacer(1, 16))

    sig_data = [
        [
            Paragraph("<b>Student Signature:</b> ______________________", cell_style),
            Paragraph("<b>Verified By (Faculty/HOD):</b> ______________________", ParagraphStyle('SigR', fontName='Helvetica', fontSize=8, leading=10.5, alignment=2, textColor=colors.HexColor('#1e293b'))),
        ]
    ]
    sig_t = Table(sig_data, colWidths=[260, 263])
    elements.append(KeepTogether(sig_t))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# 6. CONSOLIDATED FEEDBACK ANALYTICS REPORT PDF
# ─────────────────────────────────────────────
def generate_feedback_analytics_pdf(feedback_form):
    """
    Generates an official Consolidated Feedback Analytics & Summary Report
    for HOD and College Administration.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=13, leading=15, alignment=1, textColor=colors.HexColor('#800000'))
    sub_style    = ParagraphStyle('Sub',   fontName='Helvetica', fontSize=8, leading=11, alignment=1, textColor=colors.HexColor('#475569'))
    banner_style = ParagraphStyle('Bnr',   fontName='Helvetica-Bold', fontSize=10.5, leading=13, alignment=1, textColor=colors.HexColor('#1e293b'))
    cell_style   = ParagraphStyle('Cell',  fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#1e293b'))
    bold_style   = ParagraphStyle('Bold',  fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0f172a'))
    center_bold  = ParagraphStyle('CBold', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1, textColor=colors.HexColor('#0f172a'))
    hdr_style    = ParagraphStyle('Hdr',   fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.white)

    elements = []

    # 1. Header
    elements.append(Paragraph("<b>VASIREDDY VENKATADRI INSTITUTE OF TECHNOLOGY</b>", title_style))
    elements.append(Paragraph("Autonomous Institution &middot; NAAC 'A' Grade &middot; NBA Accredited", sub_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#800000'), spaceAfter=5))
    elements.append(Paragraph("<b>CONSOLIDATED STUDENT FEEDBACK ANALYTICAL REPORT</b>", banner_style))
    elements.append(Paragraph(f"<b>Title:</b> {feedback_form.title} &middot; Target: {feedback_form.target_display}", sub_style))
    elements.append(Spacer(1, 8))

    # 2. Key Metrics Summary Box
    total_subs = feedback_form.total_submissions_count()
    overall_avg = feedback_form.get_average_rating()
    rating_pct = round((overall_avg / 5.0) * 100, 1) if overall_avg > 0 else 0.0

    kpi_data = [
        [
            Paragraph(f"<b>Total Submissions:</b><br/><font size=11 color='#800000'><b>{total_subs}</b></font>", center_bold),
            Paragraph(f"<b>Overall Average Score:</b><br/><font size=11 color='#059669'><b>{overall_avg} / 5.0</b></font>", center_bold),
            Paragraph(f"<b>Satisfaction Index:</b><br/><font size=11 color='#2563eb'><b>{rating_pct}%</b></font>", center_bold),
            Paragraph(f"<b>Status:</b><br/><font size=9><b>{'Active' if feedback_form.is_active else 'Closed'}</b></font>", center_bold),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[130, 131, 131, 131])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    # 3. Question Breakdown Table
    questions = feedback_form.questions.all().order_by('order', 'id')
    q_data = [
        [
            Paragraph("<b>S.No</b>", hdr_style),
            Paragraph("<b>Evaluation Parameter / Question</b>", ParagraphStyle('HdrL', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=0, textColor=colors.white)),
            Paragraph("<b>Type</b>", hdr_style),
            Paragraph("<b>Avg Score (out of 5)</b>", hdr_style),
            Paragraph("<b>Score %</b>", hdr_style),
        ]
    ]

    for idx, q in enumerate(questions, 1):
        if q.question_type == 'rating_5':
            avg_score = q.get_average_score()
            pct = f"{round((avg_score / 5.0) * 100, 1)}%" if avg_score > 0 else "0%"
            score_display = f"{avg_score} / 5.0"
        elif q.question_type == 'rating_10':
            avg_score = q.get_average_score()
            pct = f"{round((avg_score / 10.0) * 100, 1)}%" if avg_score > 0 else "0%"
            score_display = f"{avg_score} / 10.0"
        else:
            ans_count = q.answers.count()
            score_display = f"{ans_count} Responses"
            pct = "-"

        q_data.append([
            Paragraph(str(idx), center_bold),
            Paragraph(f"<b>{q.question_text}</b>", cell_style),
            Paragraph(q.get_question_type_display(), cell_style),
            Paragraph(f"<b>{score_display}</b>", center_bold),
            Paragraph(f"<b>{pct}</b>", center_bold),
        ])

    table_breakdown = Table(q_data, colWidths=[30, 273, 90, 75, 55], repeatRows=1)
    table_breakdown.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#800000')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fbfcfd')]),
    ]))
    elements.append(table_breakdown)
    elements.append(Spacer(1, 14))

    # 4. Recent Submissions Roster
    submissions = feedback_form.submissions.select_related('student__user', 'student__branch', 'student__section').order_by('-submitted_at')[:40]
    if submissions.exists():
        sub_data = [
            [
                Paragraph("<b>S.No</b>", hdr_style),
                Paragraph("<b>Roll Number</b>", hdr_style),
                Paragraph("<b>Student Name</b>", ParagraphStyle('HdrL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=0, textColor=colors.white)),
                Paragraph("<b>Section</b>", hdr_style),
                Paragraph("<b>Submitted At</b>", hdr_style),
                Paragraph("<b>Avg Rating</b>", hdr_style),
                Paragraph("<b>Ref No</b>", hdr_style),
            ]
        ]
        for s_idx, sub in enumerate(submissions, 1):
            sec_lbl = sub.student.section.name if sub.student.section else "-"
            sub_data.append([
                Paragraph(str(s_idx), center_bold),
                Paragraph(sub.student.roll_number, center_bold),
                Paragraph(sub.student.user.get_full_name(), cell_style),
                Paragraph(sec_lbl, center_bold),
                Paragraph(sub.submitted_at.strftime('%d-%b %I:%M %p'), cell_style),
                Paragraph(f"{sub.average_rating} ★", center_bold),
                Paragraph(sub.reference_no, ParagraphStyle('Ref', fontName='Helvetica', fontSize=7, leading=8, alignment=1, textColor=colors.HexColor('#64748b'))),
            ])
        sub_table = Table(sub_data, colWidths=[25, 80, 135, 45, 95, 55, 88], repeatRows=1)
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        elements.append(KeepTogether(sub_table))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer

