from django.contrib.auth import get_user_model
from django.db.models import Q, Avg
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Skill, UserSkill, Match, SwapChain, Message, Session, Rating
from .serializers import (
    RegisterSerializer, UserPublicSerializer, ProfileUpdateSerializer,
    SkillSerializer, UserSkillSerializer, MatchSerializer, SwapChainSerializer,
    MessageSerializer, SessionSerializer, RatingSerializer,
)

User = get_user_model()


# ─── Auth ─────────────────────────────────────────────────────────────────────

class SignupView(generics.CreateAPIView):
    """POST /api/signup — Register a new user, return JWT tokens."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserPublicSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "message": "Account created successfully.",
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/login — Authenticate and return JWT tokens."""
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
        return Response({
            "user": UserPublicSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class LogoutView(APIView):
    """POST /api/logout — Blacklist the refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."})
        except Exception:
            return Response({"error": "Invalid token."}, status=400)


# ─── User / Profile ───────────────────────────────────────────────────────────

class MeView(APIView):
    """GET /api/me — Get current user profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserPublicSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPublicSerializer(request.user).data)


class UserDetailView(generics.RetrieveAPIView):
    """GET /api/users/<id> — Public profile of any user."""
    queryset = User.objects.all()
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]


# ─── Skills ───────────────────────────────────────────────────────────────────

class SkillListView(generics.ListCreateAPIView):
    """GET /api/skills — List all skills. POST to create a global skill."""
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
    """POST /api/add-skill — Add a skill to the current user's profile."""
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MySkillsView(generics.ListAPIView):
    """GET /api/my-skills — Get current user's skills."""
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user).select_related("skill")


class DeleteSkillView(generics.DestroyAPIView):
    """DELETE /api/my-skills/<id> — Remove a skill from current user."""
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user)


# ─── Matching ─────────────────────────────────────────────────────────────────

class MatchListView(APIView):
    """GET /api/matches — Get all matches for current user (direct + AI + chain)."""
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
    """POST /api/run-matching — Run AI matching engine for current user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .matching import find_direct_matches, find_ai_matches, find_chain_matches

        all_users = User.objects.exclude(id=request.user.id).prefetch_related("user_skills__skill")
        results = {"direct": [], "ai": [], "chain": []}

        # Direct matches
        direct = find_direct_matches(request.user, all_users)
        for m in direct:
            match, created = Match.objects.get_or_create(
                user1=request.user,
                user2=m["user"],
                defaults={"type": "direct", "similarity_score": 100.0}
            )
            results["direct"].append(MatchSerializer(match).data)

        # AI matches
        try:
            ai_matches = find_ai_matches(request.user, all_users)
            for m in ai_matches:
                match, created = Match.objects.get_or_create(
                    user1=request.user,
                    user2=m["user"],
                    defaults={"type": "ai", "similarity_score": m["similarity_score"]}
                )
                if not created and match.similarity_score != m["similarity_score"]:
                    match.similarity_score = m["similarity_score"]
                    match.save()
                results["ai"].append(MatchSerializer(match).data)
        except Exception as e:
            results["ai_error"] = str(e)

        # Chain matches
        chains = find_chain_matches(list(all_users) + [request.user])
        for chain in chains:
            if request.user in chain:
                u1, u2, u3 = chain[0], chain[1], chain[2]
                chain_obj, _ = SwapChain.objects.get_or_create(user1=u1, user2=u2, user3=u3)
                results["chain"].append(SwapChainSerializer(chain_obj).data)

        return Response(results)


class SimilarityScoreView(APIView):
    """POST /api/similarity — Compute AI similarity between two skill names."""
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
    """POST /api/request-swap — Send a swap request to another user."""
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
            user1=request.user,
            user2=target,
            defaults={"status": "pending", "type": request.data.get("type", "direct")}
        )

        if not created and match.status == "pending":
            return Response({"message": "Request already sent.", "match": MatchSerializer(match).data})

        return Response({
            "message": "Swap request sent." if created else "Match already exists.",
            "match": MatchSerializer(match).data
        }, status=201 if created else 200)


class AcceptRequestView(APIView):
    """POST /api/accept-request — Accept or reject a swap request."""
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
        else:
            return Response({"error": "action must be 'accept' or 'reject'."}, status=400)


# ─── Messages ─────────────────────────────────────────────────────────────────

class SendMessageView(generics.CreateAPIView):
    """POST /api/send-message — Send a chat message."""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class ConversationView(APIView):
    """GET /api/messages/<user_id> — Get chat history with a user."""
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

        # Mark incoming as read
        messages.filter(receiver=request.user, is_read=False).update(is_read=True)

        return Response(MessageSerializer(messages, many=True).data)


class InboxView(APIView):
    """GET /api/inbox — Get list of conversations (latest message per contact)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all users the current user has chatted with
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
                unread_count = Message.objects.filter(
                    sender=contact, receiver=request.user, is_read=False
                ).count()
                contacts.append({
                    "user": UserPublicSerializer(contact).data,
                    "last_message": MessageSerializer(last_msg).data if last_msg else None,
                    "unread_count": unread_count,
                })
            except User.DoesNotExist:
                pass

        return Response(contacts)


# ─── Sessions ─────────────────────────────────────────────────────────────────

class SessionListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/sessions — List or create sessions."""
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
    """GET/PATCH/DELETE /api/sessions/<id>"""
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Session.objects.filter(
            Q(host=self.request.user) | Q(guest=self.request.user)
        )


class StartSessionView(APIView):
    """POST /api/sessions/<id>/start — Start a session, get Agora token."""
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
            "agora_app_id": getattr(__import__("django.conf", fromlist=["settings"]).settings, "AGORA_APP_ID", ""),
        })


# ─── Ratings ──────────────────────────────────────────────────────────────────

class RateUserView(generics.CreateAPIView):
    """POST /api/rate — Submit a rating after a session."""
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        session = serializer.validated_data["session"]
        if session.host != self.request.user and session.guest != self.request.user:
            raise PermissionError("You were not part of this session.")
        rated = session.guest if session.host == self.request.user else session.host
        rating = serializer.save(rater=self.request.user, rated_user=rated)

        # Update user's average rating
        avg = Rating.objects.filter(rated_user=rated).aggregate(Avg("score"))["score__avg"] or 0
        rated.rating = round(avg, 1)
        rated.save()


class ChainListView(generics.ListAPIView):
    """GET /api/chains — Get all chain swaps involving the current user."""
    serializer_class = SwapChainSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        return SwapChain.objects.filter(Q(user1=u) | Q(user2=u) | Q(user3=u))


class AcceptChainView(APIView):
    """POST /api/chains/<id>/accept — Accept a chain swap."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            chain = SwapChain.objects.get(pk=pk)
        except SwapChain.DoesNotExist:
            return Response({"error": "Chain not found."}, status=404)
        chain.status = "active"
        chain.save()
        return Response(SwapChainSerializer(chain).data)
