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
    current_level = models.IntegerField(default=0)  # For level-based scheduling
    
    course = models.ForeignKey('Course', on_delete=models.CASCADE, null=True, blank=True)
    is_paused = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'problem', 'course')

    def reset_progress(self):
        from django.utils import timezone
        self.difficulty = 0.0
        self.stability = 0.0
        self.last_review_date = None
        self.next_review_date = timezone.now()
        self.total_reviews = 0
        self.current_level = 0
        self.save()
        self.logs.all().delete()

    def __str__(self):
        course_name = self.course.name if self.course else "General"
        return f"{self.user.username} - {self.problem.title} ({course_name})"

class ReviewLog(models.Model):
    RATING_CHOICES = [(1, 'Fail'), (2, 'Pass')]
    record = models.ForeignKey(UserProblemRecord, on_delete=models.CASCADE, related_name='logs')
    review_date = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(choices=RATING_CHOICES)  # FSRS input
    time_spent = models.DurationField(null=True, blank=True)  # Optional timing
    user_insight = models.TextField(blank=True)  # Key takeaway from the session

    def __str__(self):
        return f"Review for {self.record.problem.title} on {self.review_date.strftime('%Y-%m-%d')}"

class Course(models.Model):
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('cpp', 'C++'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    problems = models.ManyToManyField(Problem, related_name='courses')
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='python')
    is_paused = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
