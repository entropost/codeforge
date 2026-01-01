from django import forms
from .models import Problem, ReviewLog, Course

class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['source', 'source_id', 'title', 'url', 'difficulty']

class ReviewForm(forms.ModelForm):
    class Meta:
        model = ReviewLog
        fields = ['rating', 'time_spent', 'user_insight']

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'description', 'language']
