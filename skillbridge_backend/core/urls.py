from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────
    path("signup",            views.SignupView.as_view(),          name="signup"),
    path("login",             views.LoginView.as_view(),           name="login"),
    path("logout",            views.LogoutView.as_view(),          name="logout"),
    path("token/refresh",     TokenRefreshView.as_view(),          name="token_refresh"),

    # ── User / Profile ────────────────────────────────────
    path("me",                views.MeView.as_view(),              name="me"),
    path("users/<int:pk>",    views.UserDetailView.as_view(),      name="user_detail"),

    # ── Skills ────────────────────────────────────────────
    path("skills",            views.SkillListView.as_view(),       name="skill_list"),
    path("add-skill",         views.AddSkillView.as_view(),        name="add_skill"),
    path("my-skills",         views.MySkillsView.as_view(),        name="my_skills"),
    path("my-skills/<int:pk>",views.DeleteSkillView.as_view(),     name="delete_skill"),

    # ── Matching ──────────────────────────────────────────
    path("matches",           views.MatchListView.as_view(),       name="matches"),
    path("run-matching",      views.RunMatchingView.as_view(),     name="run_matching"),
    path("similarity",        views.SimilarityScoreView.as_view(), name="similarity"),

    # ── Swap Requests ─────────────────────────────────────
    path("request-swap",      views.RequestSwapView.as_view(),     name="request_swap"),
    path("accept-request/<int:match_id>",
                              views.AcceptRequestView.as_view(),   name="accept_request"),

    # ── Chat / Messages ───────────────────────────────────
    path("send-message",      views.SendMessageView.as_view(),     name="send_message"),
    path("inbox",             views.InboxView.as_view(),           name="inbox"),
    path("messages/<int:user_id>",
                              views.ConversationView.as_view(),    name="conversation"),

    # ── Sessions (Video) ──────────────────────────────────
    path("sessions",          views.SessionListCreateView.as_view(),   name="sessions"),
    path("sessions/<int:pk>", views.SessionDetailView.as_view(),       name="session_detail"),
    path("sessions/<int:pk>/start",
                              views.StartSessionView.as_view(),        name="start_session"),

    # ── Chain Swaps ───────────────────────────────────────
    path("chains",            views.ChainListView.as_view(),           name="chains"),
    path("chains/<int:pk>/accept",
                              views.AcceptChainView.as_view(),         name="accept_chain"),

    # ── Ratings ───────────────────────────────────────────
    path("rate",              views.RateUserView.as_view(),            name="rate"),
]
