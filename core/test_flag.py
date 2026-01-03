from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from core.models import Problem, Course, UserProblemRecord
from core.services import PracticeFileManager, GitManager
import os
from pathlib import Path
import shutil

class PracticeRepoFlagTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.course = Course.objects.create(user=self.user, name="Test Course", language='py')
        self.problem = Problem.objects.create(
            source='LC',
            source_id='test-prob',
            title='Test Prob',
            url='https://leetcode.com/problems/test-prob/',
            difficulty='Easy'
        )
        self.record = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course
        )
        self.test_practice_dir = "/tmp/codeforge_test_practice"
        if os.path.exists(self.test_practice_dir):
            shutil.rmtree(self.test_practice_dir)
        os.makedirs(self.test_practice_dir)

    def tearDown(self):
        if os.path.exists(self.test_practice_dir):
            shutil.rmtree(self.test_practice_dir)

    @override_settings(ENABLE_PRACTICE_REPO=False, PRACTICE_DIRECTORY="/tmp/codeforge_test_practice")
    def test_flag_disabled(self):
        # Verify PracticeFileManager returns None when flag is disabled
        file_path = PracticeFileManager.create_practice_file(self.record)
        self.assertIsNone(file_path)
        
        # Verify no directory/file was created
        self.assertEqual(len(os.listdir(self.test_practice_dir)), 0)

    @override_settings(ENABLE_PRACTICE_REPO=True, PRACTICE_DIRECTORY="/tmp/codeforge_test_practice")
    def test_flag_enabled(self):
        # Verify PracticeFileManager creates file when flag is enabled
        file_path = PracticeFileManager.create_practice_file(self.record)
        self.assertIsNotNone(file_path)
        self.assertTrue(os.path.exists(file_path))
        
        # Verify content
        with open(file_path, 'r') as f:
            content = f.read()
            self.assertIn("Problem: Test Prob", content)
