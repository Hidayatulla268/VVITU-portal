#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Redirect legacy DJANGO_SETTINGS_MODULE values from vvit_portal to VVITU_Portal
    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
    if settings_module and settings_module.startswith('vvit_portal'):
        os.environ['DJANGO_SETTINGS_MODULE'] = settings_module.replace('vvit_portal', 'VVITU_Portal')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
