from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, PlatformViewSet, QueryView

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'platforms', PlatformViewSet, basename='platform')

urlpatterns = [
    path('', include(router.urls)),
    path('query/', QueryView.as_view(), name='query'),
]
