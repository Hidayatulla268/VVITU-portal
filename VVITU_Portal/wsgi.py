import os
from django.core.wsgi import get_wsgi_application

# Redirect legacy DJANGO_SETTINGS_MODULE values from vvit_portal to VVITU_Portal
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
if settings_module and settings_module.startswith('vvit_portal'):
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module.replace('vvit_portal', 'VVITU_Portal')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
application = get_wsgi_application()
