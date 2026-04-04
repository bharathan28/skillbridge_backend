"""
AI Matching Engine — SkillSwap AI
Uses OpenAI text-embedding-3-small for skill similarity scoring.
"""
import os
import numpy as np
from django.conf import settings

try:
    import openai
    openai.api_key = settings.OPENAI_API_KEY   # <-- SET YOUR KEY IN .env as OPENAI_API_KEY
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# ─── Embedding & Similarity ──────────────────────────────────────────────────

def get_embedding(text: str) -> list:
    """Get OpenAI embedding for a skill name."""
    if not OPENAI_AVAILABLE:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-3-small",   # 1536 dimensions, cheap + fast
        input=text.strip().lower()
    )
    return response.data[0].embedding


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Cosine similarity between two embedding vectors. Returns 0.0–1.0."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def compute_skill_similarity(skill_a: str, skill_b: str) -> float:
    """
    Returns a 0–100 similarity score between two skill names.
    Example: compute_skill_similarity("Python", "Data Science") -> 87.4
    """
    emb_a = get_embedding(skill_a)
    emb_b = get_embedding(skill_b)
    score = cosine_similarity(emb_a, emb_b)
    return round(score * 100, 1)


# ─── Direct Matching ─────────────────────────────────────────────────────────

def find_direct_matches(current_user, all_users):
    """
    1-to-1 exact match:
    current_user.teach ∩ other.learn  AND  current_user.learn ∩ other.teach

    Returns list of dicts: [{user, teach_skills, learn_skills, type}]
    """
    from .models import UserSkill

    my_teach = set(
        UserSkill.objects.filter(user=current_user, type="teach")
        .values_list("skill__name", flat=True)
    )
    my_learn = set(
        UserSkill.objects.filter(user=current_user, type="learn")
        .values_list("skill__name", flat=True)
    )

    matches = []
    for other in all_users:
        if other.id == current_user.id:
            continue
        their_teach = set(
            UserSkill.objects.filter(user=other, type="teach")
            .values_list("skill__name", flat=True)
        )
        their_learn = set(
            UserSkill.objects.filter(user=other, type="learn")
            .values_list("skill__name", flat=True)
        )
        can_get = my_learn & their_teach     # they teach what I want
        can_give = my_teach & their_learn    # I teach what they want

        if can_get and can_give:
            matches.append({
                "user": other,
                "type": "direct",
                "teach_match": list(can_get),
                "learn_match": list(can_give),
                "similarity_score": 100.0,
            })

    return matches


# ─── AI Matching ─────────────────────────────────────────────────────────────

def find_ai_matches(current_user, all_users, threshold: float = 55.0):
    """
    Semantic matching using OpenAI embeddings + cosine similarity.
    Finds users whose skills are similar even if not exact word match.
    Example: "Python" ~ "Data Science" = 87%

    Returns list sorted by score descending.
    """
    from .models import UserSkill

    my_teach_skills = list(
        UserSkill.objects.filter(user=current_user, type="teach")
        .values_list("skill__name", flat=True)
    )
    my_learn_skills = list(
        UserSkill.objects.filter(user=current_user, type="learn")
        .values_list("skill__name", flat=True)
    )

    if not my_teach_skills or not my_learn_skills:
        return []

    matches = []
    for other in all_users:
        if other.id == current_user.id:
            continue

        their_learn = list(
            UserSkill.objects.filter(user=other, type="learn")
            .values_list("skill__name", flat=True)
        )
        their_teach = list(
            UserSkill.objects.filter(user=other, type="teach")
            .values_list("skill__name", flat=True)
        )

        if not their_learn or not their_teach:
            continue

        # Score: how well can I teach what they want + how well they teach what I want
        teach_scores = []
        for my_skill in my_teach_skills:
            for their_skill in their_learn:
                try:
                    score = compute_skill_similarity(my_skill, their_skill)
                    teach_scores.append(score)
                except Exception:
                    pass

        learn_scores = []
        for my_skill in my_learn_skills:
            for their_skill in their_teach:
                try:
                    score = compute_skill_similarity(my_skill, their_skill)
                    learn_scores.append(score)
                except Exception:
                    pass

        if not teach_scores or not learn_scores:
            continue

        overall_score = (max(teach_scores) + max(learn_scores)) / 2

        if overall_score >= threshold:
            matches.append({
                "user": other,
                "type": "ai",
                "similarity_score": round(overall_score, 1),
            })

    return sorted(matches, key=lambda x: x["similarity_score"], reverse=True)


# ─── Chain Matching (DFS) ────────────────────────────────────────────────────

def find_chain_matches(all_users, max_chain_length: int = 3):
    """
    Detect skill-swap cycles using DFS on a directed skill graph.
    Cycle: A teaches B something, B teaches C something, C teaches A something.
    Chain length capped at 3 per TDD spec.

    Returns list of chains: [[user_a, user_b, user_c], ...]
    """
    from .models import UserSkill

    # Build skill maps
    user_teach_map = {}
    user_learn_map = {}
    for user in all_users:
        user_teach_map[user.id] = set(
            UserSkill.objects.filter(user=user, type="teach")
            .values_list("skill__name", flat=True)
        )
        user_learn_map[user.id] = set(
            UserSkill.objects.filter(user=user, type="learn")
            .values_list("skill__name", flat=True)
        )

    # Build directed adjacency: edge A->B means A teaches something B wants
    def has_edge(uid_a, uid_b):
        return bool(user_teach_map.get(uid_a, set()) & user_learn_map.get(uid_b, set()))

    id_to_user = {u.id: u for u in all_users}
    user_ids = [u.id for u in all_users]

    chains = []
    seen_chains = set()

    def dfs(start_id, current_id, path):
        if len(path) == max_chain_length:
            # Check if last node has edge back to start (cycle complete)
            if has_edge(current_id, start_id):
                key = frozenset(path)
                if key not in seen_chains:
                    seen_chains.add(key)
                    chains.append([id_to_user[uid] for uid in path])
            return
        for next_id in user_ids:
            if next_id not in path and next_id != start_id:
                if has_edge(current_id, next_id):
                    dfs(start_id, next_id, path + [next_id])

    for uid in user_ids:
        dfs(uid, uid, [uid])

    return chains


# ─── Agora Token Generation ───────────────────────────────────────────────────

def generate_agora_token(channel_name: str, uid: int = 0) -> str:
    """
    Generate Agora RTC token for a video channel.
    Requires AGORA_APP_ID and AGORA_APP_CERTIFICATE in settings.
    Falls back to empty string (dev mode uses no-auth Agora).
    """
    try:
        from agora_token_builder import RtcTokenBuilder, Role_Publisher
        import time
        app_id = settings.AGORA_APP_ID
        app_cert = settings.AGORA_APP_CERTIFICATE
        if not app_id or not app_cert:
            return ""
        expire_time = int(time.time()) + 3600  # 1 hour
        return RtcTokenBuilder.buildTokenWithUid(
            app_id, app_cert, channel_name, uid, Role_Publisher, expire_time
        )
    except Exception:
        return ""
