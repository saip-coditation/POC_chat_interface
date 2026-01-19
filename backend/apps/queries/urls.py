"""
Query URL Configuration
"""

from django.urls import path
from .views import ProcessQueryView, QueryHistoryView

urlpatterns = [
    path('process/', ProcessQueryView.as_view(), name='process_query'),
    path('history/', QueryHistoryView.as_view(), name='query_history'),
]
