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
                elif 'codeforces.com' in url:
                    data = ProblemFetcher.fetch_codeforces(url)
                else:
                    return render(request, 'core/add_problem.html', {'error': 'Only LeetCode and Codeforces URLs supported'})
                
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
            
            # Git Commit
            fm = FileManager()
            commit_message = f"Review: {record.problem.title} (Rating: {review.get_rating_display()})"
            try:
                commit_hash = fm.commit_solution(record.file_path, commit_message)
                review.commit_hash = commit_hash
                review.save()
            except Exception as e:
                # Log error or handle gracefully
                print(f"Git commit failed: {e}")

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
    
    # Recent Activity
    recent_reviews = ReviewLog.objects.select_related('record__problem').order_by('-review_date')[:5]
    
    # Tags Breakdown
    from django.db.models import Count
    # This is a bit tricky with JSONField, but we can do a simple count of primary tags
    all_records = UserProblemRecord.objects.select_related('problem')
    tag_counts = {}
    for r in all_records:
        tags = r.problem.pattern_tags
        if tags:
            primary = tags[0]
            tag_counts[primary] = tag_counts.get(primary, 0) + 1
            
    context = {
        'total_problems': total_problems,
        'due_today': due_today,
        'total_reviews': total_reviews,
        'recent_reviews': recent_reviews,
        'tag_counts': tag_counts
    }
    return render(request, 'core/dashboard.html', context)
