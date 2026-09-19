"""
VVITU Portal — Document & Photo Question Extraction Engine
Extracts evaluation criteria, questionnaire questions, titles, and instructions
from uploaded documents (PDFs and Photos/Images) and converts them into structured online feedback forms.
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path_or_bytes) -> Dict[str, Any]:
    """
    Extracts structured text and tabular content from a PDF document using pdfplumber and pypdf.
    """
    extracted_text = []
    tables_found = []

    # 1. Try pdfplumber for high fidelity text & table extraction
    try:
        import pdfplumber
        with pdfplumber.open(file_path_or_bytes) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text(layout=True) or page.extract_text() or ""
                if page_text.strip():
                    extracted_text.append(page_text.strip())
                
                # Extract tables (common in feedback evaluation grids)
                page_tables = page.extract_tables()
                if page_tables:
                    for tbl in page_tables:
                        cleaned_rows = []
                        for row in tbl:
                            cleaned_row = [str(c).strip() if c is not None else "" for c in row]
                            if any(cleaned_row):
                                cleaned_rows.append(cleaned_row)
                        if cleaned_rows:
                            tables_found.append(cleaned_rows)
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed or not available: {e}")

    # 2. Fallback / supplement with pypdf if text is empty
    if not extracted_text:
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path_or_bytes)
            for page in reader.pages:
                t = page.extract_text()
                if t and t.strip():
                    extracted_text.append(t.strip())
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e}")

    full_text = "\n\n".join(extracted_text)
    return {
        "text": full_text,
        "tables": tables_found,
    }


def extract_text_from_image(file_path_or_bytes) -> Dict[str, Any]:
    """
    Extracts text from an image (photo JPG/PNG) using available OCR / AI tools.
    """
    full_text = ""
    tables = []

    # 1. Try Google Generative AI (Gemini Vision) if available and configured
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            # Read bytes
            if hasattr(file_path_or_bytes, 'read'):
                file_path_or_bytes.seek(0)
                img_data = file_path_or_bytes.read()
            elif isinstance(file_path_or_bytes, str):
                with open(file_path_or_bytes, 'rb') as f:
                    img_data = f.read()
            else:
                img_data = bytes(file_path_or_bytes)

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg'),
                    "Extract all text, titles, instructions, evaluation criteria, and numbered feedback questionnaire questions verbatim from this feedback form document image. Keep question numbers."
                ]
            )
            if response and response.text:
                full_text = response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini Vision extraction failed: {e}")

    # 2. Try pytesseract with automatic binary path discovery
    if not full_text:
        try:
            import pytesseract
            from PIL import Image
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Users\HP\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
                r'C:\tools\tesseract\tesseract.exe',
            ]
            for t_path in tesseract_paths:
                if os.path.exists(t_path):
                    pytesseract.pytesseract.tesseract_cmd = t_path
                    break
            img = Image.open(file_path_or_bytes)
            full_text = pytesseract.image_to_string(img)
        except Exception as e:
            logger.debug(f"Pytesseract not available or failed: {e}")

    return {
        "text": full_text,
        "tables": tables,
    }


def classify_feedback_type(text: str) -> str:
    """Classifies the feedback type based on content keywords."""
    lower = text.lower()
    if any(k in lower for k in ['faculty', 'teacher', 'teaching', 'instructor', 'professor', 'lecture', 'subject teacher']):
        return 'faculty'
    if any(k in lower for k in ['curriculum', 'course', 'parent feedback', 'syllabus', 'outcome', 'cos', 'pos']):
        return 'course'
    if any(k in lower for k in ['infrastructure', 'facility', 'facilities', 'lab', 'library', 'hostel', 'canteen', 'campus', 'wifi', 'sanitation']):
        return 'institutional'
    return 'general'


def detect_question_type(q_text: str) -> tuple[str, str]:
    """
    Detects question type: ('rating_5', 'rating_10', 'choice', 'text') and any parsed options.
    """
    lower = q_text.lower()

    # Open ended feedback / Suggestions
    if any(k in lower for k in ['any additional suggestions', 'any other feedback', 'any comments', 'write your remarks', 'suggestions, ideas or comments']):
        return ('text', '')

    # Yes / No & Choice Questions (e.g. "Do you support...", "Are there any...", "Is it important...", "Should the curriculum...", "Does the curriculum...")
    if any(k in lower for k in ['yes/no', 'yes or no', '(yes/no)', '[yes/no]', 'response (yes/no)']):
        return ('choice', 'Yes, No')
    if any(lower.startswith(prefix) for prefix in ['do you ', 'are there ', 'is it ', 'should the ', 'does the ', 'would you ', 'can the ']):
        return ('choice', 'Yes, No')
    if any(k in lower for k in ['agree/disagree', 'agree or disagree']):
        return ('choice', 'Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree')

    # Detect inline choices like (a) ... (b) ... or [1] ... [2] ...
    choice_match = re.findall(r'[\(\[](?:[A-Da-d1-4])[\)\]]\s*([^\(\[\]\)]+)', q_text)
    if len(choice_match) >= 2:
        options_str = ", ".join([opt.strip() for opt in choice_match if opt.strip()])
        return ('choice', options_str)

    # 10-point scale questions
    if any(k in lower for k in ['1 to 10', '1-10', 'out of 10', 'scale 1-10', 'score (1-10)']):
        return ('rating_10', '')

    # Text / Comments / Written questions
    if any(k in lower for k in ['comments', 'suggestions', 'remarks', 'specify', 'describe', 'explain', 'opinion', 'write your']):
        return ('text', '')
    if q_text.rstrip().endswith('______') or '[text]' in lower or '(descriptive)' in lower:
        return ('text', '')

    # Default to standard 5-point rating scale
    return ('rating_5', '')


def parse_questionnaire_structure(text: str, tables: Optional[List[List[List[str]]]] = None) -> Dict[str, Any]:
    """
    Intelligently parses unstructured raw text and table rows into a structured feedback form:
    - Form Title
    - Instructions / Description
    - Feedback Category
    - Array of Questions (with text, type, options, required, order)
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    title = ""
    description = ""
    questions: List[Dict[str, Any]] = []

    # 1. Identify Title
    # Look for header lines containing "feedback", "evaluation", "survey", "questionnaire", or uppercase lines
    title_candidates = []
    desc_lines = []

    for i, line in enumerate(lines[:12]):
        clean_l = re.sub(r'^[#*_\-\s]+|[#*_\-\s]+$', '', line).strip()
        lower_l = clean_l.lower()
        if any(k in lower_l for k in ['feedback form', 'evaluation form', 'survey', 'questionnaire', 'performance evaluation', 'feedback on']):
            title_candidates.append(clean_l)
        elif clean_l.isupper() and len(clean_l) > 10 and len(clean_l) < 100:
            title_candidates.append(clean_l)
        elif any(k in lower_l for k in ['instruction', 'guideline', 'note:', 'scale:', 'please rate', 'dear student', 'give your']):
            desc_lines.append(clean_l)

    if title_candidates:
        title = title_candidates[0]
        # Clean title
        title = re.sub(r'^(department of [^–\-—]+[–\-—]\s*)', '', title, flags=re.IGNORECASE)
    else:
        # Generic title based on classification
        fb_type = classify_feedback_type(text)
        type_names = {
            'faculty': 'Faculty Teaching & Performance Evaluation',
            'course': 'Course Curriculum & Syllabus Feedback',
            'institutional': 'Institutional Facilities & Infrastructure Feedback',
            'general': 'Student Feedback & Evaluation Form',
        }
        title = type_names.get(fb_type, 'Student Feedback & Evaluation Form')

    # 2. Identify Description / Instructions
    if desc_lines:
        description = " ".join(desc_lines[:3])
    else:
        description = "Please review each parameter below and provide your honest feedback."

    # 3. Extract Questions from Tabular Grids (if present)
    if tables:
        for table in tables:
            for row in table:
                if len(row) < 2:
                    continue
                # Skip header rows (e.g. "S.No", "Parameter", "5", "4", "3", "2", "1")
                row_str = " ".join(row).lower()
                if any(h in row_str for h in ['s.no', 'sl.no', 'sno', 'parameter', 'criteria', 'particulars']) and ('5' in row_str or 'rating' in row_str or 'score' in row_str):
                    continue
                
                # Check if first col is number or second col is parameter description
                q_candidate = ""
                for cell in row:
                    c_clean = cell.strip()
                    # If this cell is a sentence/phrase > 12 chars and not purely numbers/ratings
                    if len(c_clean) > 12 and not re.match(r'^[0-9\s.,\-_/★*]+$', c_clean):
                        q_candidate = c_clean
                        break
                
                if q_candidate and len(q_candidate) > 10:
                    # Clean numbering from candidate
                    cleaned_q = re.sub(r'^(?:(?:Q|Question|Sl\.?\s*No\.?|\d+)[.:)\-\s]+)+', '', q_candidate, flags=re.IGNORECASE).strip()
                    if cleaned_q and len(cleaned_q) >= 6 and not any(q['question_text'].lower() == cleaned_q.lower() for q in questions):
                        q_type, options = detect_question_type(cleaned_q)
                        questions.append({
                            'question_text': cleaned_q,
                            'question_type': q_type,
                            'options': options,
                            'is_required': True,
                            'order': len(questions) + 1
                        })

    # 4. Extract Questions from Text Lines
    # Match patterns like: "1. Clarity of...", "Q1: Faculty...", "(1) Course...", "• Teaching...", "I. Punctuality"
    q_pattern = re.compile(
        r'^(?:(?:Q(?:uestion)?\s*\d+|\d+|[I|V|X]+|\([0-9]+\)|[a-z]\))\s*[.:\-\)]|\•|\-|\*)\s*(.+)$',
        re.IGNORECASE
    )

    current_q_text = ""
    for line in lines:
        clean_line = line.strip()
        # Skip header metadata lines
        if any(clean_line.lower().startswith(skip) for skip in ['name of', 'roll no', 'date:', 'branch:', 'semester:', 'academic year:', 'signature']):
            continue

        match = q_pattern.match(clean_line)
        if match:
            # Save previous question if any
            if current_q_text:
                cleaned_text = re.sub(r'\s+', ' ', current_q_text).strip()
                # Clean trailing rating scales e.g. "(1 2 3 4 5)" or "[5 4 3 2 1]"
                cleaned_text = re.sub(r'[\(\[]\s*(?:[1-5]\s*)+[\)\]]$', '', cleaned_text).strip()
                if len(cleaned_text) >= 6 and not any(q['question_text'].lower() == cleaned_text.lower() for q in questions):
                    q_type, options = detect_question_type(cleaned_text)
                    questions.append({
                        'question_text': cleaned_text,
                        'question_type': q_type,
                        'options': options,
                        'is_required': True,
                        'order': len(questions) + 1
                    })
            current_q_text = match.group(1).strip()
        else:
            # Check if this line is continuation of previous question or a standalone question
            if current_q_text:
                # If short line or continuation
                if not any(k in clean_line.lower() for k in ['section', 'part b', 'overall rating', 'signature']):
                    # Check if line looks like rating indicators (e.g. "Excellent Good Fair Poor")
                    if not re.match(r'^(?:excellent|good|fair|average|poor|satisfactory|\d|\s|★|–|-)+$', clean_line, re.IGNORECASE):
                        current_q_text += " " + clean_line
            else:
                # Check for criteria ending with question mark or criteria keywords
                if clean_line.endswith('?') and len(clean_line) > 15:
                    q_type, options = detect_question_type(clean_line)
                    questions.append({
                        'question_text': clean_line,
                        'question_type': q_type,
                        'options': options,
                        'is_required': True,
                        'order': len(questions) + 1
                    })

    # Flush last question
    if current_q_text:
        cleaned_text = re.sub(r'\s+', ' ', current_q_text).strip()
        cleaned_text = re.sub(r'[\(\[]\s*(?:[1-5]\s*)+[\)\]]$', '', cleaned_text).strip()
        if len(cleaned_text) >= 6 and not any(q['question_text'].lower() == cleaned_text.lower() for q in questions):
            q_type, options = detect_question_type(cleaned_text)
            questions.append({
                'question_text': cleaned_text,
                'question_type': q_type,
                'options': options,
                'is_required': True,
                'order': len(questions) + 1
            })

    # 5. If no questions could be parsed from format, fallback to parsing meaningful clauses or preset
    if not questions:
        # Try finding sentences with evaluation keywords
        for line in lines:
            if len(line) > 20 and any(k in line.lower() for k in ['ability', 'punctuality', 'clarity', 'coverage', 'assessment', 'interaction', 'knowledge', 'syllabus', 'guidance', 'practical', 'cleanliness', 'satisfaction', 'quality']):
                cleaned_line = re.sub(r'^[0-9.:\-\s]+', '', line).strip()
                if len(cleaned_line) > 10 and not any(q['question_text'].lower() == cleaned_line.lower() for q in questions):
                    q_type, options = detect_question_type(cleaned_line)
                    questions.append({
                        'question_text': cleaned_line,
                        'question_type': q_type,
                        'options': options,
                        'is_required': True,
                        'order': len(questions) + 1
                    })

    # Deduplicate and re-index orders
    final_questions = []
    seen = set()
    for idx, q in enumerate(questions, start=1):
        norm = q['question_text'].strip().lower()
        if norm not in seen and len(norm) >= 5:
            seen.add(norm)
            q['order'] = len(final_questions) + 1
            final_questions.append(q)

    feedback_type = classify_feedback_type(f"{title} {description} " + " ".join([q['question_text'] for q in final_questions]))

    return {
        "success": True,
        "title": title,
        "description": description,
        "feedback_type": feedback_type,
        "questions_count": len(final_questions),
        "questions": final_questions,
        "raw_text_preview": text[:1000] if text else "",
    }


def extract_feedback_form_data(file_obj, filename: str) -> Dict[str, Any]:
    """
    Main entry point: Extracts structured questions and form metadata from an uploaded file
    (image JPG/PNG/WEBP or PDF).
    """
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.pdf':
        extracted = extract_text_from_pdf(file_obj)
        raw_text = extracted.get('text', '')
        tables = extracted.get('tables', [])
        return parse_questionnaire_structure(raw_text, tables=tables)
    elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']:
        extracted = extract_text_from_image(file_obj)
        raw_text = extracted.get('text', '')
        tables = extracted.get('tables', [])
        return parse_questionnaire_structure(raw_text, tables=tables)
    else:
        return {
            "success": False,
            "error": f"Unsupported file type '{ext}'. Please upload a PDF or Image (JPG, PNG, WEBP)."
        }
