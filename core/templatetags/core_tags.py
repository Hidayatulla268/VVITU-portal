"""
VVIT Portal — Core Template Tags

Custom Django template filters used across templates:
  • dict_get : access dict values with a variable key (e.g., in timetable grid)
  • split    : split a string by a delimiter (e.g., comma-separated day names)
"""

from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """
    Retrieve a value from a dict using a variable key in a template.

    Usage: {{ my_dict|dict_get:variable_key }}
    """
    if isinstance(d, dict):
        return d.get(key)
    return None


@register.filter(name='get_item')
def get_item(d, key):
    """Alias for dict_get for template compatibility."""
    return dict_get(d, key)


@register.filter
def split(value, delimiter=','):
    """
    Split a string by a delimiter and return the resulting list.

    Usage: {% for day in "Monday,Tuesday,Wednesday"|split:"," %}

    Useful for iterating over hardcoded CSV strings without creating
    a Python variable in every view that needs it.
    """
    return value.split(delimiter)


@register.filter
def subtract(value, arg):
    """Subtract arg from value — useful for simple arithmetic in templates."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def to_range(value):
    """Convert an integer to a Python range so templates can iterate over it."""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return []


@register.filter
def subject_icon(subject_name):
    """Returns a fontawesome icon class based on subject title."""
    if not subject_name:
        return 'fas fa-book'
    s = str(subject_name).lower()
    if any(k in s for k in ['physic', 'mechanic', 'machin']):
        return 'fas fa-cog'
    elif any(k in s for k in ['ui', 'ux', 'design', 'cad', 'drawing']):
        return 'fas fa-drafting-compass'
    elif any(k in s for k in ['data struct', 'code', 'python', 'java', 'c++', 'program', 'algorithm', 'software']):
        return 'fas fa-code'
    elif any(k in s for k in ['database', 'dbms', 'sql', 'oracle', 'big data']):
        return 'fas fa-database'
    elif any(k in s for k in ['security', 'cyber', 'crypto', 'network']):
        return 'fas fa-shield-alt'
    elif any(k in s for k in ['math', 'calculus', 'algebra', 'statistic', 'discrete', 'probability']):
        return 'fas fa-calculator'
    elif any(k in s for k in ['ai', 'neural', 'machine learn', 'deep learn', 'intelligence']):
        return 'fas fa-brain'
    elif any(k in s for k in ['web', 'html', 'react', 'full stack']):
        return 'fas fa-laptop-code'
    elif any(k in s for k in ['circuit', 'electronic', 'vlsi', 'embed', 'digital']):
        return 'fas fa-microchip'
    elif any(k in s for k in ['lab', 'practical', 'workshop']):
        return 'fas fa-flask'
    return 'fas fa-graduation-cap'

