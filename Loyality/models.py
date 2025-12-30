# backend/loyalty/models.py
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class LoyaltyProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_profile",
    )
    stamps = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.stamps} штампов"

    def add_stamp(self, count=1):
        max_stamps = getattr(settings, "LOYALTY_MAX_STAMPS", 6)
        if self.stamps >= max_stamps:
            return False
        self.stamps = min(self.stamps + count, max_stamps)
        self.save(update_fields=["stamps", "updated_at"])
        return True

    def reset_stamps(self):
        self.stamps = 0
        self.save(update_fields=["stamps", "updated_at"])
class User(AbstractUser):
    name  = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    is_barista = models.BooleanField(default=False)

    employee_code = models.CharField(
        max_length=20, unique=True,
        null=True, blank=True, default=None
    )

    # переопределяем related_name, чтобы не конфликтовать
    groups = models.ManyToManyField('auth.Group', related_name='custom_user_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='custom_user_permissions', blank=True)
class LoyaltyCode(models.Model):
    """Код на штамп(ы) лояльности (одноразовый, с TTL)."""
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code       = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    redeemed   = models.BooleanField(default=False)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_by = models.ForeignKey(  # ← новое поле
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activated_codes"
    )

    def is_valid(self) -> bool:
        return timezone.now() < self.expires_at

    def is_used(self) -> bool:
        return self.redeemed

    def __str__(self):
        return f"{self.code} for {self.user}"


class LoyaltyStamp(models.Model):
    """Один штамп = одна запись (удобно считать)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="loyalty_stamps",
        on_delete=models.CASCADE
    )
    source     = models.CharField(max_length=32, blank=True, default="code")  # откуда штамп
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(  # ← новое поле: кто начислил
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="given_stamps"
    )

    def __str__(self):
        return f"Stamp for {self.user} at {self.created_at:%Y-%m-%d %H:%M}"    