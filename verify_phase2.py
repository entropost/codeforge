import os
import django
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeforge.settings')
django.setup()

from django.test import Client
from core.models import Problem, UserProblemRecord
from core.services import FSRSScheduler, FileManager

def run_verification():
    c = Client()
    
    print("1. Testing Problem Fetcher (Mocked)...")
    with patch('core.services.requests.post') as mock_post:
        # Mock LeetCode GraphQL response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'question': {
                    'questionId': '1',
                    'title': 'Two Sum',
                    'difficulty': 'Easy',
                    'topicTags': [{'name': 'Array'}, {'name': 'Hash Table'}]
                }
            }
        }
        mock_post.return_value = mock_response
        
        response = c.post('/add/', {'url': 'https://leetcode.com/problems/two-sum/'})
        
        if response.status_code == 302:
            print("SUCCESS: Redirected after adding problem.")
        else:
            print(f"FAILED: Expected redirect, got {response.status_code}")
            print(f"Response content: {response.content.decode()}")
            return

    problem = Problem.objects.get(source_id='two-sum')
    print(f"SUCCESS: Problem '{problem.title}' created with tags {problem.pattern_tags}.")
    
    print("\n2. Testing File Creation...")
    record = UserProblemRecord.objects.get(problem=problem)
    if os.path.exists(record.file_path):
        print(f"SUCCESS: File created at {record.file_path}")
    else:
        print(f"FAILED: File not found at {record.file_path}")

    print("\n3. Testing FSRS Scheduling...")
    # Initial state
    print(f"Initial Next Review: {record.next_review_date}")
    
    # Log a review (Rating: 3 - Good)
    response = c.post(f'/review/{record.id}/', {
        'rating': 3,
        'user_insight': 'Easy peasy'
    })
    
    record.refresh_from_db()
    print(f"Post-Review Next Review: {record.next_review_date}")
    
    # Check if scheduled in the future (FSRS usually schedules 'Good' for a few days out initially)
    if record.next_review_date > timezone.now():
        print("SUCCESS: FSRS updated next_review_date to future.")
    else:
        print("FAILED: Next review date is not in the future.")

    print("\n4. Testing Dashboard...")
    response = c.get('/')
    if response.status_code == 200:
        print("SUCCESS: Dashboard loaded.")
        if b'Total Problems' in response.content:
             print("SUCCESS: Dashboard content verified.")
    else:
        print(f"FAILED: Dashboard failed with {response.status_code}")

if __name__ == '__main__':
    run_verification()
