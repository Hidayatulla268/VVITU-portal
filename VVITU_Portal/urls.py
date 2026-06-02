from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
