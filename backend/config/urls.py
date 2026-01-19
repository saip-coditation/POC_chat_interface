"""
URL configuration for DataBridge AI backend.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/platforms/', include('apps.platforms.urls')),
    path('api/queries/', include('apps.queries.urls')),
    
    # Serve Frontend
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static('/css/', document_root=settings.BASE_DIR.parent / 'css')
    urlpatterns += static('/js/', document_root=settings.BASE_DIR.parent / 'js')
    urlpatterns += static('/assets/', document_root=settings.BASE_DIR.parent / 'assets')
    # This allows index.html to find css/xxx.css and js/xxx.js directly

