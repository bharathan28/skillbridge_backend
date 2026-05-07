from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Skill, UserSkill, Match, SwapChain, Message, Session, Rating
import uuid

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    full_name  = serializers.ReadOnlyField()
    initials   = serializers.ReadOnlyField()
    is_profile_complete = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "full_name", "initials", "rating", "total_sessions",
                  "bio", "created_at", "is_profile_complete"]
        read_only_fields = ["id", "rating", "total_sessions", "created_at"]

    def get_is_profile_complete(self, obj):
        return bool(obj.first_name and obj.last_name and obj.bio)


class RegisterSerializer(serializers.ModelSerializer):
    """Only email + password required at sign-up."""
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ["email", "password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        email    = validated_data["email"].strip().lower()
        username = email.split("@")[0] + "_" + uuid.uuid4().hex[:4]
        return User.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
        )


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["first_name", "last_name", "bio", "profile_picture"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Skill
        fields = ["id", "name", "category", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSkillSerializer(serializers.ModelSerializer):
    skill      = SkillSerializer(read_only=True)
    skill_id   = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="skill", write_only=True, required=False)
    skill_name     = serializers.CharField(write_only=True, required=False)
    skill_category = serializers.CharField(write_only=True, required=False)

    class Meta:
        model  = UserSkill
        fields = ["id", "skill", "skill_id", "skill_name", "skill_category",
                  "type", "level", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        skill_name     = validated_data.pop("skill_name", None)
        skill_category = validated_data.pop("skill_category", "other")
        if skill_name and "skill" not in validated_data:
            skill, _ = Skill.objects.get_or_create(
                name=skill_name.strip().lower().title(),
                defaults={"category": skill_category}
            )
            validated_data["skill"] = skill
        return super().create(validated_data)


class MatchSerializer(serializers.ModelSerializer):
    user1            = UserPublicSerializer(read_only=True)
    user2            = UserPublicSerializer(read_only=True)
    user1_teach_skill = SkillSerializer(read_only=True)
    user1_learn_skill = SkillSerializer(read_only=True)

    class Meta:
        model  = Match
        fields = ["id", "user1", "user2", "status", "type", "similarity_score",
                  "user1_teach_skill", "user1_learn_skill", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SwapChainSerializer(serializers.ModelSerializer):
    user1     = UserPublicSerializer(read_only=True)
    user2     = UserPublicSerializer(read_only=True)
    user3     = UserPublicSerializer(read_only=True)
    skill_1to2 = SkillSerializer(read_only=True)
    skill_2to3 = SkillSerializer(read_only=True)
    skill_3to1 = SkillSerializer(read_only=True)

    class Meta:
        model  = SwapChain
        fields = ["id", "user1", "user2", "user3", "skill_1to2", "skill_2to3",
                  "skill_3to1", "status", "created_at"]
        read_only_fields = ["id", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    sender      = UserPublicSerializer(read_only=True)
    receiver    = UserPublicSerializer(read_only=True)
    receiver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="receiver", write_only=True)

    class Meta:
        model  = Message
        fields = ["id", "sender", "receiver", "receiver_id",
                  "content", "timestamp", "is_read"]
        read_only_fields = ["id", "sender", "timestamp"]


class SessionSerializer(serializers.ModelSerializer):
    host     = UserPublicSerializer(read_only=True)
    guest    = UserPublicSerializer(read_only=True)
    skill    = SkillSerializer(read_only=True)
    guest_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="guest", write_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="skill", write_only=True, required=False)

    class Meta:
        model  = Session
        fields = ["id", "match", "host", "guest", "guest_id", "skill", "skill_id",
                  "topic", "scheduled_at", "duration_minutes", "status",
                  "agora_channel", "notes", "created_at"]
        read_only_fields = ["id", "host", "agora_channel", "created_at"]


class RatingSerializer(serializers.ModelSerializer):
    rater      = UserPublicSerializer(read_only=True)
    rated_user = UserPublicSerializer(read_only=True)

    class Meta:
        model  = Rating
        fields = ["id", "session", "rater", "rated_user", "score", "comment", "created_at"]
        read_only_fields = ["id", "rater", "created_at"]
