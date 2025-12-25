import os
import django
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeforge.settings')
django.setup()

from django.test import Client
from core.models import Problem, UserProblemRecord, ReviewLog
from core.services import FileManager
import git

def run_verification():
    c = Client()
    
    print("1. Testing Codeforces Fetcher (Mocked)...")
    with patch('core.services.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div class="title">A. Theatre Square</div>
        <span class="tag-box">math</span>
        <span class="tag-box">*1000</span>
        """
        mock_get.return_value = mock_response
        
        response = c.post('/add/', {'url': 'https://codeforces.com/problemset/problem/1/A'})
        
        if response.status_code == 302:
            print("SUCCESS: Redirected after adding Codeforces problem.")
        else:
            print(f"FAILED: Expected redirect, got {response.status_code}")
            return

    problem = Problem.objects.get(source_id='1A')
    print(f"SUCCESS: Problem '{problem.title}' created with tags {problem.pattern_tags}.")
    
    print("\n2. Testing Git Commit on Review...")
    record = UserProblemRecord.objects.get(problem=problem)
    
    # Log a review
    response = c.post(f'/review/{record.id}/', {
        'rating': 3,
        'user_insight': 'Solved it!'
    })
    
    if response.status_code == 302:
        print("SUCCESS: Review logged.")
    else:
        print(f"FAILED: Review log failed with {response.status_code}")
        return
        
    review = ReviewLog.objects.filter(record=record).latest('review_date')
    if review.commit_hash:
        print(f"SUCCESS: Commit hash stored: {review.commit_hash}")
        
        # Verify commit in repo
        repo = git.Repo('/home/entropologist/code_practice')
        commit = repo.commit(review.commit_hash)
        print(f"SUCCESS: Commit found in repo: {commit.message}")
    else:
        print("FAILED: No commit hash stored in ReviewLog.")

    print("\n3. Testing Dashboard Enhancements...")
    response = c.get('/')
    if response.status_code == 200:
        print("SUCCESS: Dashboard loaded.")
        content = response.content.decode()
        if 'Recent Activity' in content and 'Tags Breakdown' in content:
             print("SUCCESS: Dashboard sections verified.")
        if 'Theatre Square' in content:
             print("SUCCESS: Recent activity shows the new problem.")
    else:
        print(f"FAILED: Dashboard failed with {response.status_code}")

if __name__ == '__main__':
    run_verification()
