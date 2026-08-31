from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.static import serve

urlpatterns = [
    path('admin/',          admin.site.urls),
    path('accounts/',       include('accounts.urls',             namespace='accounts')),
    path('student/',        include('student.urls',              namespace='student')),
    path('faculty/',        include('faculty.urls',              namespace='faculty')),
    path('admin-portal/',   include('admin_dashboard.urls',      namespace='admin_dashboard')),
    path('hod/',            include('hod.urls',                  namespace='hod')),
    path('deo/',            include('deo.urls',                  namespace='deo')),
    path('notifications/',  include('core.notification_urls',    namespace='notifications')),
    path('chat/',           include('core.chat_urls',            namespace='chat')),
    path('',                lambda r: redirect('accounts:login'), name='root'),

    # Media files route (serves user uploads and generated reports in all environments)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom Error Handlers — Auto-Redirect to Main Dashboard
handler404 = 'core.error_views.custom_404_view'
handler500 = 'core.error_views.custom_500_view'
handler403 = 'core.error_views.custom_403_view'
handler400 = 'core.error_views.custom_400_view'

