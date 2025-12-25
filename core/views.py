from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Problem, UserProblemRecord, ReviewLog
from .forms import ProblemForm, ReviewForm
from django.contrib.auth.models import User

# Helper to get the single user (since auth isn't fully implemented yet)
def get_user():
    user, created = User.objects.get_or_create(username='user')
    return user

def add_problem(request):
    if request.method == 'POST':
        form = ProblemForm(request.POST)
        if form.is_valid():
            problem = form.save()
            # Initialize UserProblemRecord
            UserProblemRecord.objects.create(
                user=get_user(),
                problem=problem,
                next_review_date=timezone.now() # Schedule immediately for first review
            )
            return redirect('review_queue')
    else:
        form = ProblemForm()
    return render(request, 'core/add_problem.html', {'form': form})

def review_queue(request):
    # Get problems due for review (or overdue)
    due_records = UserProblemRecord.objects.filter(
        next_review_date__lte=timezone.now()
    ).order_by('next_review_date')
    
    return render(request, 'core/review_queue.html', {'due_records': due_records})

def log_review(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.record = record
            review.save()
            
            # Update Schedule (Fixed Interval for Phase 1)
            rating = review.rating
            interval = 1 # Default
            if rating == 1: # Again
                interval = 1
            elif rating == 2: # Hard
                interval = 3
            elif rating == 3: # Good
                interval = 7
            elif rating == 4: # Easy
                interval = 14
                
            record.last_review_date = timezone.now()
            record.next_review_date = timezone.now() + timedelta(days=interval)
            record.total_reviews += 1
            record.save()
            
            return redirect('review_queue')
    else:
        form = ReviewForm()
    
    return render(request, 'core/log_review.html', {'form': form, 'record': record})
