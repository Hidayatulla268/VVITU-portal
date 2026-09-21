"""
VVITU Portal — Global Context Processors
Provides system-wide template variables such as APP_VERSION for static asset caching.
"""

def app_version(request):
    return {
        'APP_VERSION': '3.4.0'
    }


def active_theme(request):
    """
    Detects the user's active theme ('light' or 'dark') from cookies.
    Enables server-side rendering of data-theme on <html>, eliminating theme-flicker/FOUC on page load.
    """
    theme = request.COOKIES.get('vvit_theme') or request.COOKIES.get('vvit-theme') or 'dark'
    if theme not in ('light', 'dark'):
        theme = 'dark'
    return {
        'ACTIVE_THEME': theme
    }

