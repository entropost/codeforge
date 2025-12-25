from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Problem, UserProblemRecord, ReviewLog, Course
from .forms import ProblemForm, ReviewForm, CourseForm
from django.contrib.auth.models import User
from .services import ProblemFetcher, LevelScheduler

# Helper to get the single user
def get_user():
    user, created = User.objects.get_or_create(username='user')
    return user

def add_problem(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        course_id = request.POST.get('course')
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
                
                # 3. Create/Get Record
                UserProblemRecord.objects.get_or_create(
                    user=get_user(),
                    problem=problem,
                    defaults={
                        'next_review_date': timezone.now()
                    }
                )

                # 5. Add to Course if provided
                if course_id:
                    course = get_object_or_404(Course, id=course_id, user=get_user())
                    course.problems.add(problem)

                return redirect('review_queue')
                
            except Exception as e:
                courses = Course.objects.filter(user=get_user())
                return render(request, 'core/add_problem.html', {'error': str(e), 'courses': courses})
                
    courses = Course.objects.filter(user=get_user())
    return render(request, 'core/add_problem.html', {'courses': courses})

def batch_add_problems(request):
    if request.method == 'POST':
        urls_raw = request.POST.get('urls', '')
        course_id = request.POST.get('course')
        # Split by newline or comma and strip whitespace
        import re
        urls = [u.strip() for u in re.split(r'[\n,]', urls_raw) if u.strip()]
        
        results = []
        user = get_user()
        
        course = None
        if course_id:
            course = get_object_or_404(Course, id=course_id, user=user)

        for url in urls:
            try:
                # 1. Fetch Details
                if 'leetcode.com' in url:
                    data = ProblemFetcher.fetch_leetcode(url)
                elif 'codeforces.com' in url:
                    data = ProblemFetcher.fetch_codeforces(url)
                else:
                    results.append({'url': url, 'status': 'error', 'message': 'Unsupported URL'})
                    continue
                
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
                
                # 3. Create/Get Record
                UserProblemRecord.objects.get_or_create(
                    user=user,
                    problem=problem,
                    defaults={
                        'next_review_date': timezone.now()
                    }
                )

                # 5. Add to Course if provided
                if course:
                    course.problems.add(problem)

                results.append({'url': url, 'status': 'success', 'title': data['title']})
                
            except Exception as e:
                results.append({'url': url, 'status': 'error', 'message': str(e)})
        
        courses = Course.objects.filter(user=user)
        return render(request, 'core/batch_add_problems.html', {'results': results, 'courses': courses})
                
    courses = Course.objects.filter(user=get_user())
    return render(request, 'core/batch_add_problems.html', {'courses': courses})

def review_queue(request):
    course_id = request.GET.get('course')
    user = get_user()
    
    due_records = UserProblemRecord.objects.filter(
        user=user,
        next_review_date__lte=timezone.now()
    )

    if course_id:
        course = get_object_or_404(Course, id=course_id, user=user)
        due_records = due_records.filter(problem__in=course.problems.all())
    
    due_records = due_records.order_by('next_review_date')
    
    return render(request, 'core/review_queue.html', {'due_records': due_records, 'course_id': course_id})

def log_review(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.record = record
            review.save()
            
            # Update Schedule using LevelScheduler
            scheduler = LevelScheduler()
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

def all_problems(request):
    all_records = UserProblemRecord.objects.select_related('problem').order_by('next_review_date')
    return render(request, 'core/all_problems.html', {'all_records': all_records})

def reset_problem_progress(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id)
    record.reset_progress()
    return redirect(request.META.get('HTTP_REFERER', 'all_problems'))

def delete_problem(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id, user=get_user())
    problem = record.problem
    # Remove problem from all courses of this user
    user_courses = Course.objects.filter(user=get_user(), problems=problem)
    for course in user_courses:
        course.problems.remove(problem)
    
    record.delete()
    return redirect('all_problems')

def course_list(request):
    courses = Course.objects.filter(user=get_user())
    return render(request, 'core/course_list.html', {'courses': courses})

def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=get_user())
    problems = course.problems.all()
    # Get UserProblemRecords for these problems
    records = UserProblemRecord.objects.filter(user=get_user(), problem__in=problems)
    return render(request, 'core/course_detail.html', {'course': course, 'records': records})

def create_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.user = get_user()
            course.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'core/create_course.html', {'form': form})

def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=get_user())
    # Delete all problems associated with this course
    # This will also delete UserProblemRecords due to CASCADE
    for problem in course.problems.all():
        problem.delete()
    course.delete()
    return redirect('course_list')
