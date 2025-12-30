# Loyality/urls.py — полностью исправленная версия

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    # Аутентификация
    RegisterView,
    me,  # наш простой /api/me/
    ChangePasswordView,
    BaristaTokenObtainPairView,
    register_barista,
    verify_barista_code,
   
    # Профиль
    UserProfileView,

    # Лояльность
    GenerateLoyaltyCodeView,
    RedeemLoyaltyCodeView,
    AddStampToUserView,

    # ViewSet
    LoyaltyProfileViewSet,
    ResetLoyaltyView,
    CheckLoyaltyCodeView,
    get_loyalty_status,
    barista_login_with_code,
    barista_stats,    
)

# Роутер для ViewSet (если используешь)
router = DefaultRouter()
router.register(r'loyalty-profile', LoyaltyProfileViewSet, basename='loyalty-profile')

urlpatterns = [
    # JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Аутентификация
    path('register/', RegisterView.as_view(), name='register'),
    path('me/', me, name='me'),  # наш простой me
    path('change_password/', ChangePasswordView.as_view(), name='change_password'),

    # Бариста
     path('barista/login-with-code/', barista_login_with_code, name='barista-login-with-code'),
    path('barista/token/', BaristaTokenObtainPairView.as_view(), name='barista_token'),
    path('barista/register/', register_barista, name='barista-register'),
    path('barista/verify-code/', verify_barista_code, name='barista-verify-code'),
    path('barista/stats/', barista_stats, name='barista-stats'),

    # Профиль
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),

    # Лояльность
    path('loyalty/generate-code/', GenerateLoyaltyCodeView.as_view(), name='generate-loyalty-code'),
    path('loyalty/redeem-code/', RedeemLoyaltyCodeView.as_view(), name='redeem-loyalty-code'),
    path('loyalty/add-stamp/', AddStampToUserView.as_view(), name='add-stamp-to-user'),
    path('loyalty/reset/', ResetLoyaltyView.as_view(), name='loyalty-reset'),
    path('loyalty/check-code/', CheckLoyaltyCodeView.as_view(), name='check-loyalty-code'),
    path('loyalty/status/', get_loyalty_status, name='loyalty-status'),
] + router.urls