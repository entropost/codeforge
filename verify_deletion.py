import os
import django
from django.test import Client
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeforge.settings')
django.setup()

from core.models import Problem, UserProblemRecord, User

def run_verification():
    c = Client()
    user, _ = User.objects.get_or_create(username='user')
    
    print("1. Creating a test problem and record...")
    problem, _ = Problem.objects.get_or_create(
        source='LC',
        source_id='test-delete',
        defaults={
            'title': 'Test Delete Problem',
            'url': 'https://leetcode.com/problems/test-delete/',
            'difficulty': 'Easy',
            'pattern_tags': ['Test']
        }
    )
    
    record, _ = UserProblemRecord.objects.get_or_create(
        user=user,
        problem=problem,
        defaults={
            'next_review_date': timezone.now()
        }
    )
    
    record_id = record.id
    print(f"SUCCESS: Created record with ID {record_id}")
    
    print("\n2. Verifying record exists in database...")
    if UserProblemRecord.objects.filter(id=record_id).exists():
        print("SUCCESS: Record exists.")
    else:
        print("FAILED: Record does not exist.")
        return

    print("\n3. Calling delete view...")
    response = c.get(f'/delete/{record_id}/')
    
    if response.status_code == 302:
        print("SUCCESS: Redirected after deletion.")
    else:
        print(f"FAILED: Expected redirect, got {response.status_code}")
        return

    print("\n4. Verifying record no longer exists in database...")
    if not UserProblemRecord.objects.filter(id=record_id).exists():
        print("SUCCESS: Record deleted.")
    else:
        print("FAILED: Record still exists.")
        return

    print("\nVerification Complete: Problem deletion works correctly.")

if __name__ == '__main__':
    run_verification()
