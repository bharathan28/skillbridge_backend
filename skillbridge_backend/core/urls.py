from django.urls import path
from .views import (
    SignupView, LoginView, LogoutView, ForgotPasswordView, ResetPasswordView,
    MeView, UserDetailView,
    SkillListView, AddSkillView, MySkillsView, DeleteSkillView,
    MatchListView, RunMatchingView, SimilarityScoreView,
    RequestSwapView, AcceptRequestView,
    SendMessageView, ConversationView, InboxView,
    SessionListCreateView, SessionDetailView, StartSessionView,
    RateUserView, ChainListView, AcceptChainView,
)

urlpatterns = [
    # Auth
    path("signup",              SignupView.as_view()),
    path("login",               LoginView.as_view()),
    path("logout",              LogoutView.as_view()),
    path("forgot-password",     ForgotPasswordView.as_view()),
    path("reset-password",      ResetPasswordView.as_view()),

    # Profile
    path("me",                  MeView.as_view()),
    path("users/<int:pk>",      UserDetailView.as_view()),

    # Skills
    path("skills",              SkillListView.as_view()),
    path("add-skill",           AddSkillView.as_view()),
    path("my-skills",           MySkillsView.as_view()),
    path("my-skills/<int:pk>",  DeleteSkillView.as_view()),

    # Matching
    path("matches",             MatchListView.as_view()),
    path("run-matching",        RunMatchingView.as_view()),
    path("similarity",          SimilarityScoreView.as_view()),

    # Swap requests
    path("request-swap",        RequestSwapView.as_view()),
    path("accept-request/<int:match_id>", AcceptRequestView.as_view()),

    # Messages
    path("send-message",        SendMessageView.as_view()),
    path("messages/<int:user_id>", ConversationView.as_view()),
    path("inbox",               InboxView.as_view()),

    # Sessions
    path("sessions",            SessionListCreateView.as_view()),
    path("sessions/<int:pk>",   SessionDetailView.as_view()),
    path("sessions/<int:pk>/start", StartSessionView.as_view()),

    # Ratings & Chains
    path("rate",                RateUserView.as_view()),
    path("chains",              ChainListView.as_view()),
    path("chains/<int:pk>/accept", AcceptChainView.as_view()),
]
