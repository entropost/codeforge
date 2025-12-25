from django.db import models
from django.contrib.auth.models import User

class Problem(models.Model):
    SOURCE_CHOICES = [('LC', 'LeetCode'), ('CF', 'Codeforces')]
    source = models.CharField(max_length=2, choices=SOURCE_CHOICES)
    source_id = models.CharField(max_length=50)  # 'two-sum' or '123A'
    title = models.CharField(max_length=255)
    url = models.URLField()
    difficulty = models.CharField(max_length=10)  # Easy, Medium, Hard
    pattern_tags = models.JSONField(default=list)  # e.g., ['Hash Map', 'Two Pointers']
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('source', 'source_id')

    def __str__(self):
        return f"{self.get_source_display()} - {self.title}"

class UserProblemRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    # --- FSRS State Parameters (Initialized on first review) ---
    difficulty = models.FloatField(default=0.0)   # D (How hard the card is)
    stability = models.FloatField(default=0.0)    # S (Memory retention strength)
    last_review_date = models.DateTimeField(null=True, blank=True)
    next_review_date = models.DateTimeField(null=True, blank=True)     # The key scheduling field
    # --- Additional Tracking ---
    total_reviews = models.IntegerField(default=0)
    file_path = models.CharField(max_length=500, blank=True)  # Path to primary solution file

    def __str__(self):
        return f"{self.user.username} - {self.problem.title}"

class ReviewLog(models.Model):
    RATING_CHOICES = [(1, 'Again'), (2, 'Hard'), (3, 'Good'), (4, 'Easy')]
    record = models.ForeignKey(UserProblemRecord, on_delete=models.CASCADE, related_name='logs')
    review_date = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(choices=RATING_CHOICES)  # FSRS input
    time_spent = models.DurationField(null=True, blank=True)  # Optional timing
    user_insight = models.TextField(blank=True)  # Key takeaway from the session
    # --- Git Integration ---
    commit_hash = models.CharField(max_length=64, blank=True)  # SHA of the associated commit
    solution_snapshot = models.TextField(blank=True)  # Optional: final code from file

    def __str__(self):
        return f"Review for {self.record.problem.title} on {self.review_date.strftime('%Y-%m-%d')}"
