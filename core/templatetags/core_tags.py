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

    This is necessary because Django templates do not natively support
    dict[var] syntax — only dict.key lookups.
    """
    if isinstance(d, dict):
        return d.get(key)
    return None


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
