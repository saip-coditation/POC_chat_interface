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
    WorkflowListCreateView,
    WorkflowDetailView,
    WorkflowExecuteView,
    WorkflowExecutionListView,
    QuerySuggestionsView,
)

urlpatterns = [
    path('process/', ProcessQueryView.as_view(), name='process_query'),
    path('history/', QueryHistoryView.as_view(), name='query_history'),
    path('saved-queries/', SavedQueryListCreateView.as_view(), name='saved_query_list_create'),
    path('saved-queries/<int:pk>/', SavedQueryDestroyView.as_view(), name='saved_query_destroy'),
    path('autocomplete/', QueryAutocompleteView.as_view(), name='query_autocomplete'),
    # Workflows
    path('workflows/', WorkflowListCreateView.as_view(), name='workflow_list_create'),
    path('workflows/<uuid:pk>/', WorkflowDetailView.as_view(), name='workflow_detail'),
    path('workflows/<uuid:pk>/execute/', WorkflowExecuteView.as_view(), name='workflow_execute'),
    path('workflows/<uuid:pk>/executions/', WorkflowExecutionListView.as_view(), name='workflow_executions'),
    # Query Suggestions
    path('suggestions/', QuerySuggestionsView.as_view(), name='query_suggestions'),
]
