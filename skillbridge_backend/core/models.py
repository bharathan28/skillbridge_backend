from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, default="")
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    rating = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    total_sessions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    # username is still required for AbstractUser internals but we generate it automatically
    # first_name and last_name are optional at signup — filled during profile setup
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} <{self.email}>"

    @property
    def full_name(self):
        name = self.get_full_name().strip()
        return name if name else self.username

    @property
    def initials(self):
        parts = self.get_full_name().strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.username[:2].upper() if self.username else "?"

    @property
    def is_profile_complete(self):
        return bool(self.first_name and self.last_name and self.bio)


class Skill(models.Model):
    CATEGORY_CHOICES = [
        ("programming", "Programming"), ("design", "Design"), ("music", "Music"),
        ("language", "Language"), ("business", "Business"), ("photography", "Photography"),
        ("data_science", "Data Science"), ("marketing", "Marketing"),
        ("writing", "Writing"), ("other", "Other"),
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "skills"
        ordering = ["name"]
        unique_together = ("name", "category")

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class UserSkill(models.Model):
    TYPE_CHOICES = [("teach", "Teach"), ("learn", "Learn")]
    LEVEL_CHOICES = [(1,"Beginner"),(2,"Elementary"),(3,"Intermediate"),(4,"Advanced"),(5,"Expert")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="user_skills")
    type = models.CharField(max_length=5, choices=TYPE_CHOICES)
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_skills"
        unique_together = ("user", "skill", "type")

    def __str__(self):
        return f"{self.user.username} — {self.type} — {self.skill.name}"


class Match(models.Model):
    TYPE_CHOICES = [("direct","Direct"),("ai","AI"),("chain","Chain")]
    STATUS_CHOICES = [("pending","Pending"),("accepted","Accepted"),("rejected","Rejected"),("completed","Completed")]

    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_initiated")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_received")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    type = models.CharField(max_length=6, choices=TYPE_CHOICES, default="direct")
    similarity_score = models.FloatField(null=True, blank=True)
    user1_teach_skill = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL, related_name="matches_as_teach")
    user1_learn_skill = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL, related_name="matches_as_learn")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matches"
        unique_together = ("user1", "user2")

    def __str__(self):
        return f"{self.user1.username} <-> {self.user2.username} [{self.type}]"


class SwapChain(models.Model):
    STATUS_CHOICES = [("pending","Pending"),("active","Active"),("completed","Completed"),("cancelled","Cancelled")]

    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chains_u1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chains_u2")
    user3 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chains_u3")
    skill_1to2 = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL, related_name="chain_1to2")
    skill_2to3 = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL, related_name="chain_2to3")
    skill_3to1 = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL, related_name="chain_3to1")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "swap_chains"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "messages"
        ordering = ["timestamp"]


class Session(models.Model):
    STATUS_CHOICES = [("scheduled","Scheduled"),("active","Active"),("completed","Completed"),("cancelled","Cancelled")]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="sessions", null=True, blank=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hosted_sessions")
    guest = models.ForeignKey(User, on_delete=models.CASCADE, related_name="guest_sessions")
    skill = models.ForeignKey(Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    topic = models.CharField(max_length=200, blank=True, default="")
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="scheduled")
    agora_channel = models.CharField(max_length=100, blank=True, default="")
    agora_token = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sessions"
        ordering = ["scheduled_at"]


class Rating(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="ratings")
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_ratings")
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_ratings")
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ratings"
        unique_together = ("session", "rater")