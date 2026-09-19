from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from core import views_media as core_views_media
from student import views as student_views


urlpatterns = [
    path('admin/',          admin.site.urls),
    path('accounts/',       include('accounts.urls',             namespace='accounts')),
    path('student/',        include('student.urls',              namespace='student')),
    path('faculty/',        include('faculty.urls',              namespace='faculty')),
    path('admin-portal/',   include('admin_dashboard.urls',      namespace='admin_dashboard')),
    re_path(r'^admin-dashboard/(?P<path>.*)$', lambda r, path='': redirect(f'/admin-portal/{path}')),
    path('hod/',            include('hod.urls',                  namespace='hod')),
    path('deo/',            include('deo.urls',                  namespace='deo')),
    path('notifications/',  include('core.notification_urls',    namespace='notifications')),
    path('chat/',           include('core.chat_urls',            namespace='chat')),
    path('',                lambda r: redirect('accounts:login'), name='root'),

    path('secure-media/leave-doc/<int:leave_id>/', core_views_media.view_student_leave_document, name='view_student_leave_document'),
    path('secure-media/feedback-doc/<int:form_id>/', core_views_media.view_feedback_document, name='view_feedback_document'),
    path('academic-calendar/', student_views.academic_calendar, name='academic_calendar'),
    path('overview/', core_views_media.portal_overview, name='portal_overview'),
    path('features/', core_views_media.portal_overview, name='portal_features'),
]




# Development static & media serving
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom Error Handlers — Auto-Redirect to Main Dashboard
handler404 = 'core.error_views.custom_404_view'
handler500 = 'core.error_views.custom_500_view'
handler403 = 'core.error_views.custom_403_view'
handler400 = 'core.error_views.custom_400_view'

