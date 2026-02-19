from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DashboardViewSet, WidgetViewSet

router = DefaultRouter()
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'widgets', WidgetViewSet, basename='widget')

urlpatterns = [
    path('', include(router.urls)),
]
