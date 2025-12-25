from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Problem, UserProblemRecord, ReviewLog
from .forms import ProblemForm, ReviewForm
from django.contrib.auth.models import User
from .services import ProblemFetcher, FSRSScheduler, FileManager

# Helper to get the single user
def get_user():
    user, created = User.objects.get_or_create(username='user')
    return user

def add_problem(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        if url:
            try:
                # 1. Fetch Details
                if 'leetcode.com' in url:
                    data = ProblemFetcher.fetch_leetcode(url)
                else:
                    # Fallback or error for now
                    return render(request, 'core/add_problem.html', {'error': 'Only LeetCode URLs supported for now'})
                
                # 2. Create/Get Problem
                problem, created = Problem.objects.get_or_create(
                    source=data['source'],
                    source_id=data['source_id'],
                    defaults={
                        'title': data['title'],
                        'url': data['url'],
                        'difficulty': data['difficulty'],
                        'pattern_tags': data['pattern_tags']
                    }
                )
                
                # 3. Create File
                fm = FileManager()
                file_path = fm.create_solution_file(problem)
                
                # 4. Create/Get Record
                UserProblemRecord.objects.get_or_create(
                    user=get_user(),
                    problem=problem,
                    defaults={
                        'file_path': file_path,
                        'next_review_date': timezone.now()
                    }
                )
                return redirect('review_queue')
                
            except Exception as e:
                return render(request, 'core/add_problem.html', {'error': str(e)})
                
    return render(request, 'core/add_problem.html')

def review_queue(request):
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
            
            # Update Schedule using FSRS
            scheduler = FSRSScheduler()
            scheduler.schedule(record, review.rating)
            
            record.total_reviews += 1
            record.save()
            
            return redirect('review_queue')
    else:
        form = ReviewForm()
    
    return render(request, 'core/log_review.html', {'form': form, 'record': record})

def dashboard(request):
    total_problems = UserProblemRecord.objects.count()
    due_today = UserProblemRecord.objects.filter(next_review_date__lte=timezone.now()).count()
    total_reviews = ReviewLog.objects.count()
    
    context = {
        'total_problems': total_problems,
        'due_today': due_today,
        'total_reviews': total_reviews
    }
    return render(request, 'core/dashboard.html', context)
