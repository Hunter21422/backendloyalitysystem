# Loyality/views.py — финальная исправленная версия

import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.db.models import F

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import LoyaltyProfile, LoyaltyCode, LoyaltyStamp
from .serializers import (
    RegisterSerializer,
    ChangePasswordSerializer,
    BaristaTokenObtainPairSerializer,
    UserProfileSerializer,
)

User = get_user_model()


# ==================== ЛОЯЛЬНОСТЬ ====================

class LoyaltyProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LoyaltyProfile.objects.filter(user=self.request.user)


# ==================== АУТЕНТИФИКАЦИЯ ====================

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        user.is_staff = False
        if hasattr(user, "is_barista"):
            user.is_barista = False
        user.save()

        return Response({"detail": "Пользователь успешно зарегистрирован"}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    profile, _ = LoyaltyProfile.objects.get_or_create(user=u)
    return Response({
        "id": u.id,
        "username": u.username,
        "is_staff": bool(u.is_staff),
        "is_barista": bool(getattr(u, "is_barista", False)),
        "stamps": profile.stamps,
        "max_stamps": getattr(settings, "LOYALTY_MAX_STAMPS", 6),
    })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Старый пароль неверен"}, status=400)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Пароль успешно изменён"})


class BaristaTokenObtainPairView(TokenObtainPairView):
    serializer_class = BaristaTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user

        if not (user.is_staff or getattr(user, "is_barista", False)):
            return Response({
                "error": "Вас нет в списке барист. Обратитесь к администратору."
            }, status=403)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


# ==================== ПРОФИЛЬ ====================

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ==================== БАРИСТА ====================

@api_view(["POST"])
@permission_classes([AllowAny])
def register_barista(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password")
    invite_code = (request.data.get("employee_code") or "").strip()

    if not all([username, password, invite_code]):
        return Response({"error": "Все поля обязательны"}, status=400)

    if len(username) < 3 or len(password) < 6:
        return Response({"error": "Логин ≥3 символов, пароль ≥6"}, status=400)

    valid_codes = getattr(settings, "BARISTA_MASTER_CODES", []) or [getattr(settings, "BARISTA_MASTER_CODE", "555")]
    if invite_code not in valid_codes:
        return Response({"error": "Неверный мастер-код"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return Response({"error": "Логин уже занят"}, status=409)

    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password)
            user.is_staff = True
            if hasattr(user, "is_barista"):
                user.is_barista = True
            user.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "detail": "Бариста успешно зарегистрирован"
            }, status=201)
    except IntegrityError:
        return Response({"error": "Ошибка создания пользователя"}, status=500)


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_barista_code(request):
    code = (request.data.get("employee_code") or "").strip()
    if not code:
        return Response({"error": "Код обязателен"}, status=400)

    master_codes = getattr(settings, "BARISTA_MASTER_CODES", []) or [getattr(settings, "BARISTA_MASTER_CODE", "555")]
    if code in master_codes:
        return Response({"valid": True, "type": "master"})
    return Response({"valid": False})


@api_view(["POST"])
@permission_classes([AllowAny])
def barista_login_with_code(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password")
    employee_code = (request.data.get("employee_code") or "").strip()
    
    if not all([username, password, employee_code]):
        return Response({"error": "Все поля обязательны"}, status=400)
    
    valid_codes = getattr(settings, "BARISTA_MASTER_CODES", []) or [getattr(settings, "BARISTA_MASTER_CODE", "555")]
    if employee_code not in valid_codes:
        return Response({"error": "Неверный мастер-код сотрудника."}, status=400)
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({"error": "Пользователь не найден"}, status=404)
    
    if not user.check_password(password):
        return Response({"error": "Неверный пароль"}, status=400)
    
    if not (user.is_staff or getattr(user, "is_barista", False)):
        return Response({"error": "Вас нет в списке барист."}, status=403)
    
    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    })


# ==================== ЛОЯЛЬНОСТЬ ====================

def _unique_code(length=6):
    while True:
        code = "".join(secrets.choice(string.digits) for _ in range(length))
        if not LoyaltyCode.objects.filter(code=code, redeemed=False, expires_at__gt=timezone.now()).exists():
            return code


class GenerateLoyaltyCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = _unique_code()
        expires_at = timezone.now() + timedelta(minutes=15)
        LoyaltyCode.objects.create(user=request.user, code=code, expires_at=expires_at)
        return Response({"code": code, "expires_at": expires_at.isoformat()})


# АКТИВАЦИЯ КОДА С НАЧИСЛЕНИЕМ ШТАМПА — рабочий Redeem
class RedeemLoyaltyCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"detail": "Код обязателен"}, status=400)

        try:
            with transaction.atomic():
                lc = LoyaltyCode.objects.select_for_update().get(code=code)

                if lc.redeemed:
                    return Response({"detail": "Код уже использован"}, status=400)
                if timezone.now() > lc.expires_at:
                    return Response({"detail": "Код истёк"}, status=400)

                # Начисляем штамп клиенту
                profile, _ = LoyaltyProfile.objects.get_or_create(user=lc.user)
                profile.stamps = F("stamps") + 1
                profile.save()
                profile.refresh_from_db()

                # Активируем код
                lc.redeemed = True
                lc.redeemed_at = timezone.now()
                lc.redeemed_by = request.user
                lc.save(update_fields=["redeemed", "redeemed_at", "redeemed_by"])

                # Записываем в статистику штампов
                LoyaltyStamp.objects.create(
                    user=lc.user,
                    source="code",
                    created_by=request.user
                )

                return Response({
                    "detail": "Штамп успешно начислен",
                    "stamps": profile.stamps,
                    "client": lc.user.username
                })

        except LoyaltyCode.DoesNotExist:
            return Response({"detail": "Код не найден"}, status=404)


# РУЧНОЕ НАЧИСЛЕНИЕ ШТАМПОВ
class AddStampToUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response({"error": "Только бариста"}, status=403)

        username = request.data.get("username")
        amount = max(1, int(request.data.get("amount", 1)))

        if not username:
            return Response({"error": "username обязателен"}, status=400)

        try:
            target = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        profile, _ = LoyaltyProfile.objects.get_or_create(user=target)
        max_stamps = getattr(settings, "LOYALTY_MAX_STAMPS", 6)

        if profile.stamps + amount > max_stamps:
            amount = max_stamps - profile.stamps

        if amount <= 0:
            return Response({"detail": f"Лимит достигнут ({max_stamps})"}, status=400)

        profile.stamps = F("stamps") + amount
        profile.save()
        profile.refresh_from_db()

        for _ in range(amount):
            LoyaltyStamp.objects.create(
                user=target,
                source="manual",
                created_by=request.user
            )

        return Response({
            "username": target.username,
            "stamps_added": amount,
            "stamps_total": profile.stamps,
            "max_stamps": max_stamps
        })


class ResetLoyaltyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        username = request.data.get("username")

        if username:
            if not request.user.is_staff:
                return Response({"detail": "Только бариста"}, status=403)
            try:
                target_user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"detail": "Пользователь не найден"}, status=404)
        else:
            target_user = request.user

        profile, _ = LoyaltyProfile.objects.get_or_create(user=target_user)
        old = profile.stamps
        profile.stamps = 0
        profile.save(update_fields=["stamps"])

        return Response({
            "detail": f"Счётчик сброшен (было {old})",
            "stamps": 0,
            "max_stamps": getattr(settings, "LOYALTY_MAX_STAMPS", 6),
        })


# ПРОВЕРКА КОДА — только проверка + активация кода (для статистики "активировано кодов")
class CheckLoyaltyCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"detail": "Код обязателен"}, status=400)

        try:
            with transaction.atomic():
                lc = LoyaltyCode.objects.select_for_update().get(code=code)

                if lc.redeemed:
                    return Response({"detail": "Код уже был использован"}, status=400)
                if timezone.now() > lc.expires_at:
                    return Response({"detail": "Срок действия кода истёк"}, status=400)

                # Только активируем код — для статистики "активировано кодов"
                lc.redeemed = True
                lc.redeemed_at = timezone.now()
                lc.redeemed_by = request.user
                lc.save(update_fields=["redeemed", "redeemed_at", "redeemed_by"])

                # ШТАМП НЕ НАЧИСЛЯЕТСЯ!
                return Response({"detail": "Код валидный и активирован"}, status=200)

        except LoyaltyCode.DoesNotExist:
            return Response({"detail": "Такого кода не существует"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_loyalty_status(request):
    username = request.query_params.get("username")
    if not username:
        return Response({"detail": "username обязателен"}, status=400)

    if not request.user.is_staff:
        if request.user.username.lower() != username.lower():
            return Response({"detail": "Доступ только к своему профилю"}, status=403)

    try:
        target = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return Response({"detail": "Пользователь не найден"}, status=404)

    profile, _ = LoyaltyProfile.objects.get_or_create(user=target)
    return Response({
        "username": target.username,
        "stamps": profile.stamps,
        "max_stamps": getattr(settings, "LOYALTY_MAX_STAMPS", 6),
    })


# СТАТИСТИКА БАРИСТЫ
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def barista_stats(request):
    if not (request.user.is_staff or getattr(request.user, 'is_barista', False)):
        return Response({"detail": "Доступ запрещён"}, status=403)

    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    stats = {
        "codes_activated": LoyaltyCode.objects.filter(
            redeemed=True,
            redeemed_by=request.user
        ).count(),
        "stamps_today": LoyaltyStamp.objects.filter(
            created_at__date=today,
            created_by=request.user
        ).count(),
        "stamps_week": LoyaltyStamp.objects.filter(
            created_at__gte=week_ago,
            created_by=request.user
        ).count(),
    }

    return Response(stats)
