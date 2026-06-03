"""
VVIT Portal - Sample Data Setup Script
Run with:  python manage.py shell -c "exec(open('sample_data.py').read())"
"""

import os
import django

# Setup Django settings context
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    call_command('seed_data')
else:
    call_command('seed_data')
