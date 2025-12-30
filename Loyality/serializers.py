# backend/Loyality/serializers.py
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Правильные импорты моделей из текущего приложения
from .models import LoyaltyProfile, LoyaltyCode, LoyaltyStamp  # ← добавил LoyaltyStamp

User = get_user_model()


# --- Лояльность: профиль ---
class LoyaltyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyProfile
        fields = ["id", "user", "stamps"]
        read_only_fields = ["user", "stamps"]


# --- Публичная короткая версия пользователя ---
class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "is_staff"]


# --- Регистрация пользователя ---
class RegisterSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("username", "password", "employee_code")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        validated_data.pop("employee_code", None)
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return user


# --- Смена пароля ---
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=4)


# --- JWT для бариста ---
class BaristaTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["is_staff"] = bool(user.is_staff)
        if getattr(user, "is_staff", False):
            if hasattr(user, "name"):
                data["name"] = user.name
            if hasattr(user, "employee_code"):
                data["employee_code"] = user.employee_code
        return data


# --- Профиль пользователя ---
class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    recent_orders = serializers.JSONField(read_only=True, required=False)
    
    stamps = serializers.SerializerMethodField()
    max_stamps = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "name", "phone", "recent_orders", "stamps", "max_stamps"]
        extra_kwargs = {"username": {"read_only": True}}

    def get_stamps(self, obj):
        profile, _ = LoyaltyProfile.objects.get_or_create(user=obj)
        return int(profile.stamps or 0)

    def get_max_stamps(self, obj):
        return int(getattr(settings, "LOYALTY_MAX_STAMPS", 6))

    def validate_phone(self, value):
        if value in (None, ""):
            return ""
        if not re.fullmatch(r"[0-9+()\- \s]{6,32}", value):
            raise serializers.ValidationError("Некорректный номер телефона.")
        return value

    def update(self, instance, validated_data):
        for field in ("name", "phone"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance


# --- Короткий "me" (/api/me/) с полной статистикой для баристы ---
class MeSerializer(serializers.ModelSerializer):
    stamps = serializers.SerializerMethodField()
    max_stamps = serializers.SerializerMethodField()
    codes_activated = serializers.SerializerMethodField()
    stamps_today = serializers.SerializerMethodField()
    stamps_week = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "is_staff", "is_barista",
            "stamps", "max_stamps",
            "codes_activated", "stamps_today", "stamps_week"
        )

    def get_stamps(self, obj):
        profile, _ = LoyaltyProfile.objects.get_or_create(user=obj)
        return int(profile.stamps or 0)

    def get_max_stamps(self, obj):
        return int(getattr(settings, "LOYALTY_MAX_STAMPS", 6))

    def get_codes_activated(self, obj):
        # Если у тебя есть поле redeemed_by в LoyaltyCode — используй его:
        # return LoyaltyCode.objects.filter(redeemed=True, redeemed_by=obj).count()
        # Пока считаем все активированные коды (или по логике твоего проекта)
        return LoyaltyCode.objects.filter(redeemed=True).count()

    def get_stamps_today(self, obj):
        from django.utils import timezone
        today = timezone.now().date()
        # Если штампы привязаны к баристе — добавь фильтр redeemed_by=obj или created_by=obj
        return LoyaltyStamp.objects.filter(created_at__date=today).count()

    def get_stamps_week(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        return LoyaltyStamp.objects.filter(created_at__gte=week_ago).count()


# --- BACKWARD COMPATIBILITY ---
UserProfilePatchSerializer = UserProfileSerializer