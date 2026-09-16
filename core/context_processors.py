"""
VVITU Portal — Global Context Processors
Provides system-wide template variables such as APP_VERSION for static asset caching.
"""

def app_version(request):
    return {
        'APP_VERSION': '2.5.0'
    }
