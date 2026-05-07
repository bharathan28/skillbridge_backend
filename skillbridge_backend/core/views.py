from django.contrib.auth import get_user_model
from django.db.models import Q, Avg
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Skill, UserSkill, Match, SwapChain, Message, Session, Rating
from .serializers import (
    RegisterSerializer, UserPublicSerializer, ProfileUpdateSerializer,
    SkillSerializer, UserSkillSerializer, MatchSerializer, SwapChainSerializer,
    MessageSerializer, SessionSerializer, RatingSerializer,
)

User = get_user_model()

FRONTEND_URL = getattr(django_settings, 'FRONTEND_URL', 'https://skillbridge-frontend-fawn.vercel.app')


def send_email_safe(subject, body, to_email):
    """Send email silently — never crash the main request."""
    try:
        send_mail(
            subject,
            body,
            django_settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=True,
        )
    except Exception:
        pass


# ─── Auth ─────────────────────────────────────────────────────────────────────

class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        # Welcome email
        send_email_safe(
            "Welcome to SkillBridge 🎉",
            f"Hi {user.first_name or user.username},\n\n"
            "Your SkillBridge account has been created successfully.\n\n"
            "Start exploring and swapping skills today!\n\n"
            f"{FRONTEND_URL}\n\n— The SkillBridge Team",
            user.email,
        )

        return Response({
            "user": UserPublicSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "message": "Account created successfully.",
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not email or not password:
            return Response({"error": "Email and password are required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials."}, status=401)

        if not user.check_password(password):
            return Response({"error": "Invalid credentials."}, status=401)

        if not user.is_active:
            return Response({"error": "Account is deactivated."}, status=403)

        refresh = RefreshToken.for_user(user)

        # Login notification email
        from django.utils import timezone
        now = timezone.now().strftime("%d %b %Y at %H:%M UTC")
        send_email_safe(
            "New login to your SkillBridge account",
            f"Hi {user.first_name or user.username},\n\n"
            f"A new login was detected on your account on {now}.\n\n"
            "If this was you, no action is needed.\n"
            "If you didn't log in, please reset your password immediately.\n\n"
            f"{FRONTEND_URL}\n\n— The SkillBridge Team",
            user.email,
        )

        return Response({
            "user": UserPublicSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data["refresh"])
            token.blacklist()
            return Response({"message": "Logged out successfully."})
        except Exception:
            return Response({"error": "Invalid token."}, status=400)


class ForgotPasswordView(APIView):
    """POST /api/forgot-password — Send a password reset link."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response({"error": "Email is required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Return success anyway to prevent email enumeration
            return Response({"message": "If that email exists, a reset link has been sent."})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        send_email_safe(
            "Reset your SkillBridge password",
            f"Hi {user.first_name or user.username},\n\n"
            "You requested a password reset. Click the link below:\n\n"
            f"{reset_url}\n\n"
            "This link expires in 24 hours. If you didn't request this, ignore this email.\n\n"
            "— The SkillBridge Team",
            user.email,
        )

        return Response({"message": "If that email exists, a reset link has been sent."})


class ResetPasswordView(APIView):
    """POST /api/reset-password — Confirm password reset with token."""
    permission_classes = [AllowAny]

    def post(self, request):
        uid_b64 = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("password", "")

        if not uid_b64 or not token or not new_password:
            return Response({"error": "uid, token and password are required."}, status=400)

        if len(new_password) < 8:
            return Response({"error": "Password must be at least 8 characters."}, status=400)

        try:
            uid = urlsafe_base64_decode(uid_b64).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, Exception):
            return Response({"error": "Invalid reset link."}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Reset link has expired or is invalid."}, status=400)

        user.set_password(new_password)
        user.save()

        send_email_safe(
            "Your SkillBridge password was changed",
            f"Hi {user.first_name or user.username},\n\n"
            "Your password has been changed successfully.\n\n"
            "If you didn't do this, contact support immediately.\n\n"
            "— The SkillBridge Team",
            user.email,
        )

        return Response({"message": "Password reset successfully. You can now log in."})


# ─── User / Profile ───────────────────────────────────────────────────────────

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserPublicSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPublicSerializer(request.user).data)


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]


# ─── Skills ───────────────────────────────────────────────────────────────────

class SkillListView(generics.ListCreateAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Skill.objects.all()
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("search")
        if category:
            qs = qs.filter(category=category)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class AddSkillView(generics.CreateAPIView):
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MySkillsView(generics.ListAPIView):
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user).select_related("skill")


class DeleteSkillView(generics.DestroyAPIView):
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user)


# ─── Matching ─────────────────────────────────────────────────────────────────

class MatchListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        matches = Match.objects.filter(
            Q(user1=request.user) | Q(user2=request.user)
        ).select_related("user1", "user2", "user1_teach_skill", "user1_learn_skill")
        match_type = request.query_params.get("type")
        if match_type:
            matches = matches.filter(type=match_type)
        return Response(MatchSerializer(matches, many=True).data)


class RunMatchingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .matching import find_direct_matches, find_ai_matches, find_chain_matches

        all_users = User.objects.exclude(id=request.user.id).prefetch_related("user_skills__skill")
        results = {"direct": [], "ai": [], "chain": []}

        direct = find_direct_matches(request.user, all_users)
        for m in direct:
            match, _ = Match.objects.get_or_create(
                user1=request.user, user2=m["user"],
                defaults={"type": "direct", "similarity_score": 100.0}
            )
            results["direct"].append(MatchSerializer(match).data)

        try:
            ai_matches = find_ai_matches(request.user, all_users)
            for m in ai_matches:
                match, created = Match.objects.get_or_create(
                    user1=request.user, user2=m["user"],
                    defaults={"type": "ai", "similarity_score": m["similarity_score"]}
                )
                if not created and match.similarity_score != m["similarity_score"]:
                    match.similarity_score = m["similarity_score"]
                    match.save()
                results["ai"].append(MatchSerializer(match).data)
        except Exception as e:
            results["ai_error"] = str(e)

        chains = find_chain_matches(list(all_users) + [request.user])
        for chain in chains:
            if request.user in chain:
                u1, u2, u3 = chain[0], chain[1], chain[2]
                chain_obj, _ = SwapChain.objects.get_or_create(user1=u1, user2=u2, user3=u3)
                results["chain"].append(SwapChainSerializer(chain_obj).data)

        return Response(results)


class SimilarityScoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .matching import compute_skill_similarity
        skill_a = request.data.get("skill_a", "")
        skill_b = request.data.get("skill_b", "")
        if not skill_a or not skill_b:
            return Response({"error": "skill_a and skill_b are required."}, status=400)
        try:
            score = compute_skill_similarity(skill_a, skill_b)
            return Response({"skill_a": skill_a, "skill_b": skill_b, "score": score})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ─── Swap Requests ────────────────────────────────────────────────────────────

class RequestSwapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        target_id = request.data.get("user_id")
        if not target_id:
            return Response({"error": "user_id is required."}, status=400)
        try:
            target = User.objects.get(id=target_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        if target == request.user:
            return Response({"error": "Cannot request a swap with yourself."}, status=400)

        match, created = Match.objects.get_or_create(
            user1=request.user, user2=target,
            defaults={"status": "pending", "type": request.data.get("type", "direct")}
        )
        if not created and match.status == "pending":
            return Response({"message": "Request already sent.", "match": MatchSerializer(match).data})

        return Response({
            "message": "Swap request sent." if created else "Match already exists.",
            "match": MatchSerializer(match).data
        }, status=201 if created else 200)


class AcceptRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, match_id):
        try:
            match = Match.objects.get(id=match_id, user2=request.user, status="pending")
        except Match.DoesNotExist:
            return Response({"error": "Match not found or already processed."}, status=404)

        action = request.data.get("action", "accept")
        if action == "accept":
            match.status = "accepted"
            match.save()
            return Response({"message": "Request accepted.", "match": MatchSerializer(match).data})
        elif action == "reject":
            match.status = "rejected"
            match.save()
            return Response({"message": "Request rejected.", "match": MatchSerializer(match).data})
        return Response({"error": "action must be 'accept' or 'reject'."}, status=400)


# ─── Messages ─────────────────────────────────────────────────────────────────

class SendMessageView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class ConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            other = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        messages = Message.objects.filter(
            Q(sender=request.user, receiver=other) |
            Q(sender=other, receiver=request.user)
        ).order_by("timestamp")
        messages.filter(receiver=request.user, is_read=False).update(is_read=True)
        return Response(MessageSerializer(messages, many=True).data)


class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contact_ids = Message.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).values_list("sender_id", "receiver_id")

        unique_ids = set()
        for sid, rid in contact_ids:
            uid = rid if sid == request.user.id else sid
            unique_ids.add(uid)

        contacts = []
        for uid in unique_ids:
            try:
                contact = User.objects.get(id=uid)
                last_msg = Message.objects.filter(
                    Q(sender=request.user, receiver=contact) |
                    Q(sender=contact, receiver=request.user)
                ).order_by("-timestamp").first()
                unread = Message.objects.filter(sender=contact, receiver=request.user, is_read=False).count()
                contacts.append({
                    "user": UserPublicSerializer(contact).data,
                    "last_message": MessageSerializer(last_msg).data if last_msg else None,
                    "unread_count": unread,
                })
            except User.DoesNotExist:
                pass

        return Response(contacts)


# ─── Sessions ─────────────────────────────────────────────────────────────────

class SessionListCreateView(generics.ListCreateAPIView):
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Session.objects.filter(
            Q(host=self.request.user) | Q(guest=self.request.user)
        ).select_related("host", "guest", "skill")

    def perform_create(self, serializer):
        import uuid
        channel = f"ss-{uuid.uuid4().hex[:8]}"
        serializer.save(host=self.request.user, agora_channel=channel)


class SessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Session.objects.filter(
            Q(host=self.request.user) | Q(guest=self.request.user)
        )


class StartSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            session = Session.objects.get(
                Q(pk=pk) & (Q(host=request.user) | Q(guest=request.user))
            )
        except Session.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)

        from .matching import generate_agora_token
        session.status = "active"
        token = generate_agora_token(session.agora_channel, request.user.id)
        session.agora_token = token
        session.save()

        return Response({
            "session": SessionSerializer(session).data,
            "agora_channel": session.agora_channel,
            "agora_token": token,
            "agora_app_id": getattr(django_settings, "AGORA_APP_ID", ""),
        })


# ─── Ratings ──────────────────────────────────────────────────────────────────

class RateUserView(generics.CreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        session = serializer.validated_data["session"]
        if session.host != self.request.user and session.guest != self.request.user:
            raise PermissionError("You were not part of this session.")
        rated = session.guest if session.host == self.request.user else session.host
        serializer.save(rater=self.request.user, rated_user=rated)
        avg = Rating.objects.filter(rated_user=rated).aggregate(Avg("score"))["score__avg"] or 0
        rated.rating = round(avg, 1)
        rated.save()


class ChainListView(generics.ListAPIView):
    serializer_class = SwapChainSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        return SwapChain.objects.filter(Q(user1=u) | Q(user2=u) | Q(user3=u))


class AcceptChainView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            chain = SwapChain.objects.get(pk=pk)
        except SwapChain.DoesNotExist:
            return Response({"error": "Chain not found."}, status=404)
        chain.status = "active"
        chain.save()
        return Response(SwapChainSerializer(chain).data)
