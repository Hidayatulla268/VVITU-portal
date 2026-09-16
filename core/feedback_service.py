"""
VVITU Portal — Feedback Service & Questionnaire Templates
Shared logic for HOD and Admin Feedback Form Management and Analytics.
"""

from django.db.models import Avg, Count
from core.models import FeedbackForm, FeedbackQuestion, FeedbackSubmission, FeedbackAnswer

PRESET_TEMPLATES = {
    'faculty_10': {
        'title': 'Standard Faculty Teaching Evaluation (10 Criteria)',
        'type': 'faculty',
        'questions': [
            ("Punctuality and regularity of faculty in taking scheduled classes", "rating_5"),
            ("Clarity of explanation, depth of subject knowledge, and presentation skills", "rating_5"),
            ("Ability to engage students, encourage questions, and maintain interactive classroom discipline", "rating_5"),
            ("Fairness and transparency in internal assessment, assignment evaluation, and marks awarding", "rating_5"),
            ("Timely completion and comprehensive coverage of syllabus topics as per course plan", "rating_5"),
            ("Availability and willingness to help students outside class hours and clarify doubts", "rating_5"),
            ("Use of modern teaching aids (PPTs, board work, digital LMS resources)", "rating_5"),
            ("Relevance of examples, real-world applications, and practical case studies shared", "rating_5"),
            ("Effective guidance and mentoring during laboratory / tutorial sessions", "rating_5"),
            ("Overall satisfaction with the faculty member's teaching methodology and mentorship", "rating_5"),
        ]
    },
    'course_5': {
        'title': 'Standard Course & Curriculum Feedback',
        'type': 'course',
        'questions': [
            ("Relevance of course contents and syllabus depth to contemporary industry needs", "rating_5"),
            ("Balance between theoretical concepts and hands-on practical application", "rating_5"),
            ("Availability and quality of prescribed textbooks, reference materials, and e-learning resources", "rating_5"),
            ("Appropriateness of internal evaluation weightage, question paper standards, and exam pattern", "rating_5"),
            ("Overall effectiveness of the course in enhancing technical competence and skills", "rating_5"),
        ]
    },
    'infrastructure_6': {
        'title': 'Campus Infrastructure & Facilities Evaluation',
        'type': 'institutional',
        'questions': [
            ("Classroom infrastructure, ICT projectors, ventilation, and seating comfort", "rating_5"),
            ("Laboratory equipment condition, computing facilities, software availability, and internet/Wi-Fi", "rating_5"),
            ("Central Library resources, book accessibility, reading hall environment, and digital subscriptions", "rating_5"),
            ("Campus cleanliness, sanitation, drinking water, cafeteria hygiene, and overall environment", "rating_5"),
            ("Sports, extracurricular, and student technical club amenities", "rating_5"),
            ("Overall campus atmosphere and administrative support responsiveness", "rating_5"),
        ]
    }
}


def populate_preset_questions(form_obj, preset_key):
    """Populates standard questions for the given preset key."""
    preset = PRESET_TEMPLATES.get(preset_key)
    if not preset:
        return 0

    order = form_obj.questions.count() + 1
    created_count = 0
    for q_text, q_type in preset['questions']:
        FeedbackQuestion.objects.create(
            form=form_obj,
            question_text=q_text,
            question_type=q_type,
            is_required=True,
            order=order
        )
        order += 1
        created_count += 1
    return created_count


def get_form_analytics(form_obj):
    """
    Computes comprehensive analytics for a FeedbackForm:
    - total submissions
    - overall average rating
    - satisfaction index percentage
    - per-question averages, rating counts, score distribution
    - list of submissions
    """
    submissions = form_obj.submissions.select_related(
        'student__user', 'student__branch', 'student__year', 'student__section'
    ).order_by('-submitted_at')

    total_submissions = submissions.count()
    overall_avg = form_obj.get_average_rating()
    satisfaction_pct = round((overall_avg / 5.0) * 100, 1) if overall_avg > 0 else 0.0

    questions = form_obj.questions.all().order_by('order', 'id')
    question_stats = []

    for q in questions:
        if q.question_type in ['rating_5', 'rating_10']:
            max_scale = 5.0 if q.question_type == 'rating_5' else 10.0
            avg_val = q.get_average_score()
            pct = round((avg_val / max_scale) * 100, 1) if avg_val > 0 else 0.0
            
            # Star counts breakdown (1 to 5)
            counts = {}
            if q.question_type == 'rating_5':
                for star in range(1, 6):
                    counts[star] = q.answers.filter(rating_value=star).count()

            question_stats.append({
                'question': q,
                'avg_score': avg_val,
                'max_scale': max_scale,
                'percentage': pct,
                'counts': counts,
                'is_rating': True,
            })
        elif q.question_type == 'choice':
            choice_counts = {}
            for ans in q.answers.all():
                c_val = ans.choice_value or 'Other'
                choice_counts[c_val] = choice_counts.get(c_val, 0) + 1
            question_stats.append({
                'question': q,
                'choice_counts': choice_counts,
                'is_rating': False,
                'is_choice': True,
            })
        else: # text
            recent_texts = [a.text_value for a in q.answers.exclude(text_value__isnull=True).exclude(text_value='')[:15]]
            question_stats.append({
                'question': q,
                'text_responses': recent_texts,
                'total_responses': q.answers.exclude(text_value__isnull=True).exclude(text_value='').count(),
                'is_rating': False,
                'is_text': True,
            })

    return {
        'form': form_obj,
        'total_submissions': total_submissions,
        'overall_avg': overall_avg,
        'satisfaction_pct': satisfaction_pct,
        'question_stats': question_stats,
        'submissions': submissions,
    }
