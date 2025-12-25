from django import forms
from .models import Problem, ReviewLog

class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['source', 'source_id', 'title', 'url', 'difficulty']

class ReviewForm(forms.ModelForm):
    class Meta:
        model = ReviewLog
        fields = ['rating', 'time_spent', 'user_insight']
