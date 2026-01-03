from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Problem, UserProblemRecord, ReviewLog, Course
from .forms import ProblemForm, ReviewForm, CourseForm
from django.contrib.auth.models import User
from .services import ProblemFetcher, LevelScheduler, PracticeFileManager, GitManager
import json
from django.http import HttpResponse, JsonResponse
from django.core import serializers

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
                target_course = None
                if course_id:
                    target_course = get_object_or_404(Course, id=course_id, user=get_user())

                UserProblemRecord.objects.get_or_create(
                    user=get_user(),
                    problem=problem,
                    course=target_course,
                    defaults={
                        'next_review_date': timezone.now()
                    }
                )

                # 5. Add to Course if provided
                if target_course:
                    target_course.problems.add(problem)

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
                # 3. Create/Get Record
                UserProblemRecord.objects.get_or_create(
                    user=user,
                    problem=problem,
                    course=course,
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
        next_review_date__lte=timezone.now(),
        is_paused=False
    ).exclude(course__is_paused=True)

    if course_id:
        course = get_object_or_404(Course, id=course_id, user=user)
        due_records = due_records.filter(course=course)
    
    due_records = due_records.order_by('next_review_date')
    
    #new_problems = due_records.filter(total_reviews=0)
    pending_reviews = due_records.filter(total_reviews__gt=0)
    
    return render(request, 'core/review_queue.html', {
        #'new_problems': new_problems,
        'pending_reviews': pending_reviews,
        'course_id': course_id
    })

def log_review(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.record = record
            
            # Capture info for git commit BEFORE updating level
            status = "Pass" if review.rating == 2 else "Fail"
            course_name = record.course.name if record.course else "General"
            problem_title = record.problem.title
            level = record.current_level
            file_path = PracticeFileManager.create_practice_file(record)
            
            review.save()
            
            # Update Schedule using LevelScheduler
            scheduler = LevelScheduler()
            scheduler.schedule(record, review.rating)
            
            record.total_reviews += 1
            record.save()
            
            # Commit to git
            GitManager.commit_review(file_path, status, course_name, problem_title, level)
            
            return redirect('review_queue')
    else:
        form = ReviewForm()
    
    # Trigger practice file creation/retrieval
    practice_file_path = PracticeFileManager.create_practice_file(record)
    
    return render(request, 'core/log_review.html', {
        'form': form, 
        'record': record,
        'practice_file_path': practice_file_path
    })

def dashboard(request):
    due_records = UserProblemRecord.objects.filter(
        next_review_date__lte=timezone.now(),
        is_paused=False
    ).exclude(course__is_paused=True)
    
    total_problems = UserProblemRecord.objects.filter(is_paused=False).exclude(course__is_paused=True).count()
    due_today = due_records.count()
    new_today = due_records.filter(total_reviews=0).count()
    review_today = due_records.filter(total_reviews__gt=0).count()
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
        'new_today': new_today,
        'review_today': review_today,
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
    
    if record.course:
        record.course.problems.remove(record.problem)
    
    record.delete()
    return redirect('all_problems')

def course_list(request):
    courses = Course.objects.filter(user=get_user())
    return render(request, 'core/course_list.html', {'courses': courses})

def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=get_user())
    problems = course.problems.all()
    # Get UserProblemRecords for these problems
    records = UserProblemRecord.objects.filter(user=get_user(), course=course)
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
    # Deleting the course will automatically delete associated UserProblemRecords
    # due to the CASCADE on the UserProblemRecord.course field.
    # It also cleans up the ManyToMany relationship with Problem.
    course.delete()
    return redirect('course_list')

def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=get_user())
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = CourseForm(instance=course)
    return render(request, 'core/edit_course.html', {'form': form, 'course': course})

def import_problems(request, course_id):
    target_course = get_object_or_404(Course, id=course_id, user=get_user())
    
    if request.method == 'POST':
        source_course_id = request.POST.get('source_course')
        if source_course_id:
            source_course = get_object_or_404(Course, id=source_course_id, user=get_user())
            problems = source_course.problems.all()
            
            user = get_user()
            for problem in problems:
                # Add problem to target course
                target_course.problems.add(problem)
                
                # Create/Get UserProblemRecord for target course
                UserProblemRecord.objects.get_or_create(
                    user=user,
                    problem=problem,
                    course=target_course,
                    defaults={
                        'next_review_date': timezone.now()
                    }
                )
            
            return redirect('course_detail', course_id=target_course.id)
            
    other_courses = Course.objects.filter(user=get_user()).exclude(id=target_course.id)
    return render(request, 'core/import_problems.html', {
        'target_course': target_course,
        'other_courses': other_courses
    })

def toggle_problem_pause(request, record_id):
    record = get_object_or_404(UserProblemRecord, id=record_id, user=get_user())
    record.is_paused = not record.is_paused
    record.save()
    return redirect(request.META.get('HTTP_REFERER', 'all_problems'))

def toggle_course_pause(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=get_user())
    course.is_paused = not course.is_paused
    course.save()
    return redirect(request.META.get('HTTP_REFERER', 'course_list'))

def statistics(request):
    user = get_user()
    records = UserProblemRecord.objects.filter(user=user)
    logs = ReviewLog.objects.filter(record__user=user)
    
    # Language Breakdown
    language_counts = {}
    for r in records:
        if r.course:
            lang = r.course.get_language_display()
            language_counts[lang] = language_counts.get(lang, 0) + 1
        else:
            language_counts['General'] = language_counts.get('General', 0) + 1
            
    # Source Breakdown
    source_counts = {}
    for r in records:
        source = r.problem.get_source_display()
        source_counts[source] = source_counts.get(source, 0) + 1
        
    # Difficulty Breakdown
    difficulty_counts = {'Easy': 0, 'Medium': 0, 'Hard': 0}
    for r in records:
        diff = r.problem.difficulty
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
        
    # Level Distribution
    level_counts = {}
    for r in records:
        level = r.current_level
        level_counts[level] = level_counts.get(level, 0) + 1
    # Sort level counts by level
    level_counts = dict(sorted(level_counts.items()))
        
    # Activity (Last 30 Days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    activity_logs = logs.filter(review_date__gte=thirty_days_ago)
    
    activity_data = {}
    for i in range(30):
        date = (timezone.now() - timedelta(days=i)).date()
        activity_data[date.strftime('%Y-%m-%d')] = 0
        
    for log in activity_logs:
        date_str = log.review_date.date().strftime('%Y-%m-%d')
        if date_str in activity_data:
            activity_data[date_str] += 1
            
    # Sort activity data by date
    activity_data = dict(sorted(activity_data.items()))
    
    # Success Rate
    total_reviews = logs.count()
    pass_reviews = logs.filter(rating=2).count()
    success_rate = (pass_reviews / total_reviews * 100) if total_reviews > 0 else 0
    
    # Upcoming Reviews (Next 30 Days)
    upcoming_data = {}
    for i in range(30):
        date = (timezone.now() + timedelta(days=i)).date()
        upcoming_data[date.strftime('%Y-%m-%d')] = 0
        
    upcoming_records = records.filter(
        next_review_date__gte=timezone.now(),
        next_review_date__lte=timezone.now() + timedelta(days=30),
        is_paused=False
    ).exclude(course__is_paused=True)
    
    for r in upcoming_records:
        date_str = r.next_review_date.date().strftime('%Y-%m-%d')
        if date_str in upcoming_data:
            upcoming_data[date_str] += 1
            
    upcoming_data = dict(sorted(upcoming_data.items()))
    
    # Heatmap Data (Last 365 Days)
    today = timezone.now().date()
    one_year_ago = today - timedelta(days=365)
    
    # Get all review dates for the last year
    heatmap_logs = logs.filter(review_date__date__gte=one_year_ago)
    daily_counts = {}
    for log in heatmap_logs:
        date_str = log.review_date.date().strftime('%Y-%m-%d')
        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
    # Generate full year grid
    # We want to start from one_year_ago and go up to today
    # But for a nice grid, we might want to align to weeks. 
    # GitHub starts from one year ago, but aligns the start date to the correct weekday row.
    
    heatmap_data = []
    current_date = one_year_ago
    
    # Adjust start date to the previous Sunday (or Monday depending on preference) to align grid
    # weekday(): Mon=0, Sun=6. Let's say we want Sun as row 0.
    # If current_date is Wed (2), we want to go back 3 days to Sun.
    days_to_subtract = (current_date.weekday() + 1) % 7
    start_date = current_date - timedelta(days=days_to_subtract)
    
    # We need 53 weeks to cover a full year + padding
    for week in range(53):
        week_data = []
        for day in range(7):
            day_date = start_date + timedelta(weeks=week, days=day)
            date_str = day_date.strftime('%Y-%m-%d')
            count = daily_counts.get(date_str, 0)
            
            # Determine intensity level (0-4)
            if count == 0: intensity = 0
            elif count <= 2: intensity = 1
            elif count <= 5: intensity = 2
            elif count <= 9: intensity = 3
            else: intensity = 4
            
            week_data.append({
                'date': date_str,
                'count': count,
                'intensity': intensity,
                'in_range': one_year_ago <= day_date <= today
            })
        heatmap_data.append(week_data)

    context = {
        'total_problems': records.count(),
        'total_reviews': total_reviews,
        'success_rate': round(success_rate, 1),
        'language_counts': language_counts,
        'source_counts': source_counts,
        'difficulty_counts': difficulty_counts,
        'level_counts': level_counts,
        'activity_data': activity_data,
        'upcoming_data': upcoming_data,
        'heatmap_data': heatmap_data,
    }
    return render(request, 'core/statistics.html', context)

def review_logs(request):
    user = get_user()
    logs = ReviewLog.objects.filter(record__user=user).select_related('record__problem', 'record__course').order_by('-review_date')
    
    latest_review = logs.first()
    
    context = {
        'logs': logs,
        'latest_review': latest_review,
    }
    return render(request, 'core/review_logs.html', context)

def data_management(request):
    return render(request, 'core/data_management.html')

def export_data(request):
    user = get_user()
    
    # We want to export Problems, Courses, UserProblemRecords, and ReviewLogs
    # Problems are shared, but we only really need those associated with the user's records or courses
    records = UserProblemRecord.objects.filter(user=user)
    courses = Course.objects.filter(user=user)
    
    # Get all problems associated with these records or courses
    problem_ids = set(records.values_list('problem_id', flat=True))
    problem_ids.update(courses.values_list('problems__id', flat=True))
    problems = Problem.objects.filter(id__in=problem_ids)
    
    logs = ReviewLog.objects.filter(record__in=records)
    
    data = {
        'problems': json.loads(serializers.serialize('json', problems)),
        'courses': json.loads(serializers.serialize('json', courses)),
        'records': json.loads(serializers.serialize('json', records)),
        'logs': json.loads(serializers.serialize('json', logs)),
    }
    
    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="codeforge_export.json"'
    return response

def import_data(request):
    if request.method == 'POST' and request.FILES.get('file'):
        import_file = request.FILES['file']
        try:
            data = json.loads(import_file.read().decode('utf-8'))
            user = get_user()
            
            # 1. Import Problems
            problem_map = {} # old_id -> new_obj
            for item in data.get('problems', []):
                fields = item['fields']
                problem, created = Problem.objects.get_or_create(
                    source=fields['source'],
                    source_id=fields['source_id'],
                    defaults={
                        'title': fields['title'],
                        'url': fields['url'],
                        'difficulty': fields['difficulty'],
                        'pattern_tags': fields['pattern_tags']
                    }
                )
                problem_map[item['pk']] = problem
                
            # 2. Import Courses
            course_map = {} # old_id -> new_obj
            for item in data.get('courses', []):
                fields = item['fields']
                course, created = Course.objects.get_or_create(
                    user=user,
                    name=fields['name'],
                    defaults={
                        'description': fields['description'],
                        'language': fields['language'],
                        'is_paused': fields['is_paused']
                    }
                )
                # Add problems to course
                for old_prob_id in fields['problems']:
                    if old_prob_id in problem_map:
                        course.problems.add(problem_map[old_prob_id])
                course_map[item['pk']] = course
                
            # 3. Import UserProblemRecords
            record_map = {} # old_id -> new_obj
            for item in data.get('records', []):
                fields = item['fields']
                problem = problem_map.get(fields['problem'])
                course = course_map.get(fields['course']) if fields['course'] else None
                
                if not problem: continue
                
                record, created = UserProblemRecord.objects.get_or_create(
                    user=user,
                    problem=problem,
                    course=course,
                    defaults={
                        'difficulty': fields['difficulty'],
                        'stability': fields['stability'],
                        'last_review_date': fields['last_review_date'],
                        'next_review_date': fields['next_review_date'],
                        'total_reviews': fields['total_reviews'],
                        'current_level': fields['current_level'],
                        'is_paused': fields['is_paused']
                    }
                )
                # If it already exists, we might want to update it if the imported one is "newer"
                # For simplicity, we'll just skip if it exists for now, or we could overwrite.
                # Let's overwrite progress if the imported one has more reviews.
                if not created and fields['total_reviews'] > record.total_reviews:
                    record.difficulty = fields['difficulty']
                    record.stability = fields['stability']
                    record.last_review_date = fields['last_review_date']
                    record.next_review_date = fields['next_review_date']
                    record.total_reviews = fields['total_reviews']
                    record.current_level = fields['current_level']
                    record.is_paused = fields['is_paused']
                    record.save()
                
                record_map[item['pk']] = record
                
            # 4. Import ReviewLogs
            for item in data.get('logs', []):
                fields = item['fields']
                record = record_map.get(fields['record'])
                if not record: continue
                
                # Check if this log already exists (by date and record)
                if not ReviewLog.objects.filter(record=record, review_date=fields['review_date']).exists():
                    ReviewLog.objects.create(
                        record=record,
                        review_date=fields['review_date'],
                        rating=fields['rating'],
                        time_spent=fields['time_spent'],
                        user_insight=fields['user_insight']
                    )
            
            return render(request, 'core/data_management.html', {'success': 'Data imported successfully!'})
        except Exception as e:
            return render(request, 'core/data_management.html', {'error': f'Error importing data: {str(e)}'})
            
    return redirect('data_management')
