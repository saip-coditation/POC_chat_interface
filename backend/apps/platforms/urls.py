"""
Platform URL Configuration
"""

from django.urls import path
from .views import (
    ListPlatformsView,
    ConnectPlatformView,
    DisconnectPlatformView,
    ReverifyPlatformView,
    ZohoCodeExchangeView
)

urlpatterns = [
    path('', ListPlatformsView.as_view(), name='list_platforms'),
    path('connect/', ConnectPlatformView.as_view(), name='connect_platform'),
    path('zoho/exchange-code/', ZohoCodeExchangeView.as_view(), name='zoho_exchange_code'),
    path('<int:platform_id>/', DisconnectPlatformView.as_view(), name='disconnect_platform'),
    path('<int:platform_id>/reverify/', ReverifyPlatformView.as_view(), name='reverify_platform'),
]
