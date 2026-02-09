from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AMLDetectionViewSet, CreditAssessmentViewSet,
    InsuranceClaimViewSet, MarketAlertViewSet,
    statistics, get_modules, clear_history, health_check, metrics, prometheus_metrics,
    RegisterView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'aml', AMLDetectionViewSet)
router.register(r'credit', CreditAssessmentViewSet)
router.register(r'insurance', InsuranceClaimViewSet)
router.register(r'market', MarketAlertViewSet)

urlpatterns = [
    # Utility
    path('health/', health_check),
    path('metrics/', metrics),
    path('prometheus/', prometheus_metrics),
    path('modules/', get_modules),
    path('statistics/', statistics),
    path('clear-history/', clear_history),
    
    # Auth
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view({'post': 'create'}), name='register'),
    
    # Detection Endpoints (Map to ViewSet Create)
    path('aml/detect/', AMLDetectionViewSet.as_view({'post': 'create'})),
    path('credit/assess/', CreditAssessmentViewSet.as_view({'post': 'create'})),
    path('insurance/detect/', InsuranceClaimViewSet.as_view({'post': 'create'})),
    path('market/detect/', MarketAlertViewSet.as_view({'post': 'create'})),
    path('batch/detect/', AMLDetectionViewSet.as_view({'post': 'create'})),

    # REST APIs
    path('', include(router.urls)),
]
