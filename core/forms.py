from django import forms
from .models import Problem, ReviewLog, Course

class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['source', 'source_id', 'title', 'url', 'difficulty']

class ManualProblemForm(forms.Form):
    DIFFICULTY_CHOICES = [('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')]
    title = forms.CharField(max_length=255)
    difficulty = forms.ChoiceField(choices=DIFFICULTY_CHOICES)
    tags = forms.CharField(required=False, help_text='Comma-separated tags')
    course = forms.ModelChoiceField(queryset=Course.objects.none(), required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.filter(user=user)

class ReviewForm(forms.ModelForm):
    class Meta:
        model = ReviewLog
        fields = ['rating', 'time_spent', 'user_insight']

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'description', 'language']
