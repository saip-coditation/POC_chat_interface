"""
Query URL Configuration
"""

from django.urls import path
from .views import (
    ProcessQueryView,
    QueryHistoryView,
    SavedQueryListCreateView,
    SavedQueryDestroyView,
    QueryAutocompleteView,
)

urlpatterns = [
    path('process/', ProcessQueryView.as_view(), name='process_query'),
    path('history/', QueryHistoryView.as_view(), name='query_history'),
    path('saved-queries/', SavedQueryListCreateView.as_view(), name='saved_query_list_create'),
    path('saved-queries/<int:pk>/', SavedQueryDestroyView.as_view(), name='saved_query_destroy'),
    path('autocomplete/', QueryAutocompleteView.as_view(), name='query_autocomplete'),
]
