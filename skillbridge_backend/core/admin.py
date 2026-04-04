from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Skill, UserSkill, Match, SwapChain, Message, Session, Rating


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "username", "full_name", "rating", "total_sessions", "is_active", "created_at"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["-created_at"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SkillSwap", {"fields": ("bio", "rating", "total_sessions", "profile_picture")}),
    )


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "created_at"]
    list_filter = ["category"]
    search_fields = ["name"]


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ["user", "skill", "type", "level", "created_at"]
    list_filter = ["type", "level", "skill__category"]
    search_fields = ["user__email", "skill__name"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["user1", "user2", "type", "status", "similarity_score", "created_at"]
    list_filter = ["type", "status"]
    search_fields = ["user1__email", "user2__email"]


@admin.register(SwapChain)
class SwapChainAdmin(admin.ModelAdmin):
    list_display = ["user1", "user2", "user3", "status", "created_at"]
    list_filter = ["status"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["sender", "receiver", "content", "is_read", "timestamp"]
    list_filter = ["is_read"]
    search_fields = ["sender__email", "receiver__email"]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["host", "guest", "topic", "scheduled_at", "status", "agora_channel"]
    list_filter = ["status"]
    search_fields = ["host__email", "guest__email", "topic"]


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["rater", "rated_user", "score", "created_at"]
    list_filter = ["score"]
