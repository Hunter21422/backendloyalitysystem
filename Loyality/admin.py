# backend/loyalty/admin.py
from django.contrib import admin
from .models import  LoyaltyCode, LoyaltyStamp

@admin.register(LoyaltyCode)
class LoyaltyCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "code", "created_at", "expires_at", "redeemed")
    list_filter = ("redeemed",)
    search_fields = ("code", "user__username")

@admin.register(LoyaltyStamp)
class LoyaltyStampAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "source", "created_at")
    list_filter = ("source",)
    search_fields = ("user__username", "source")
