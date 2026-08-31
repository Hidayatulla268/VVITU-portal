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
