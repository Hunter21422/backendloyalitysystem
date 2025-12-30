# backend/loyalty/services.py
import secrets
import string
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import F
from .models import LoyaltyProfile, LoyaltyCode, LoyaltyStamp

def _generate_unique_code(length=6, alphabet=string.digits):
    """Генерация уникального кода"""
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = LoyaltyCode.objects.filter(
            code=code, 
            redeemed=False, 
            expires_at__gt=timezone.now()
        ).exists()
        if not exists:
            return code

class LoyaltyService:
    """Сервис для работы с лояльностью"""
    
    @staticmethod
    def get_or_create_profile(user):
        """Получить или создать профиль лояльности"""
        profile, created = LoyaltyProfile.objects.get_or_create(user=user)
        return profile
    
    @staticmethod
    def generate_loyalty_code(user, expires_minutes=15):
        """Сгенерировать код лояльности"""
        code = _generate_unique_code()
        expires_at = timezone.now() + timedelta(minutes=expires_minutes)
        
        loyalty_code = LoyaltyCode.objects.create(
            user=user,
            code=code,
            expires_at=expires_at
        )
        
        return loyalty_code
    
    @staticmethod
    @transaction.atomic
    def redeem_loyalty_code(code_value):
        """Активировать код лояльности"""
        try:
            loyalty_code = LoyaltyCode.objects.select_for_update().get(
                code=code_value
            )
        except LoyaltyCode.DoesNotExist:
            return False, "Код не найден"
        
        if loyalty_code.redeemed:
            return False, "Код уже использован"
        
        if not loyalty_code.is_valid():
            return False, "Срок действия кода истёк"
        
        # Активируем код
        loyalty_code.redeem()
        
        # Начисляем штамп
        profile = LoyaltyService.get_or_create_profile(loyalty_code.user)
        success, message = profile.add_stamp(1, "code_redeem")
        
        if success:
            return True, {
                "detail": "Код успешно активирован",
                "stamps_after": profile.stamps,
                "username": loyalty_code.user.username
            }
        else:
            return False, message
    
    @staticmethod
    @transaction.atomic
    def add_stamp_to_user(username, count=1, source="manual_add"):
        """Добавить штамп пользователю"""
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return False, "Пользователь не найден"
        
        profile = LoyaltyService.get_or_create_profile(user)
        success, message = profile.add_stamp(count, source)
        
        if success:
            return True, {
                "username": user.username,
                "stamps": profile.stamps,
                "stamps_added": count
            }
        else:
            return False, message
    
    @staticmethod
    @transaction.atomic
    def reset_user_stamps(username):
        """Сбросить штампы пользователя"""
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return False, "Пользователь не найден"
        
        profile = LoyaltyService.get_or_create_profile(user)
        stamps_before = profile.reset_stamps()
        
        return True, {
            "username": user.username,
            "stamps_before": stamps_before,
            "stamps_after": profile.stamps,
            "detail": f"Счётчик сброшен. Выдано вознаграждение за {stamps_before} штампов"
        }
    
    @staticmethod
    def get_user_loyalty_status(username):
        """Получить статус лояльности пользователя"""
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        
        profile, created = LoyaltyProfile.objects.get_or_create(user=user)
        
        return {
            "username": user.username,
            "stamps": profile.stamps,
            "max_stamps": getattr(settings, "LOYALTY_MAX_STAMPS", 6),
            "profile_exists": not created
        }
    
    @staticmethod
    def get_user_stamp_history(user, limit=10):
        """Получить историю штампов пользователя"""
        return LoyaltyStamp.objects.filter(user=user).order_by('-created_at')[:limit]