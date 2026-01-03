from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Problem, Course, UserProblemRecord
from django.urls import reverse

class CourseTrackingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.client = Client()
        self.client.login(username='user', password='password')
        
        self.course1 = Course.objects.create(user=self.user, name="Course 1")
        self.course2 = Course.objects.create(user=self.user, name="Course 2")
        
        self.problem = Problem.objects.create(
            source='LC',
            source_id='two-sum',
            title='Two Sum',
            url='https://leetcode.com/problems/two-sum/',
            difficulty='Easy'
        )

    def test_separate_tracking(self):
        # Create record for Course 1
        record1 = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course1
        )
        
        # Create record for Course 2
        record2 = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course2
        )
        
        self.assertEqual(UserProblemRecord.objects.count(), 2)
        self.assertNotEqual(record1.id, record2.id)
        self.assertEqual(record1.course, self.course1)
        self.assertEqual(record2.course, self.course2)

    def test_unique_constraint(self):
        UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course1
        )
        
        # Try to create another record for same course
        from django.db.utils import IntegrityError
        with self.assertRaises(IntegrityError):
            UserProblemRecord.objects.create(
                user=self.user,
                problem=self.problem,
                course=self.course1
            )

    def test_add_problem_view(self):
        # Add problem to Course 1 via view
        response = self.client.post(reverse('add_problem'), {
            'url': 'https://leetcode.com/problems/two-sum/',
            'course': self.course1.id
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify record created
        self.assertTrue(UserProblemRecord.objects.filter(user=self.user, problem__title='Two Sum', course=self.course1).exists())
        
        # Add same problem to Course 2 via view
        response = self.client.post(reverse('add_problem'), {
            'url': 'https://leetcode.com/problems/two-sum/',
            'course': self.course2.id
        })
        
        # Verify second record created
        self.assertTrue(UserProblemRecord.objects.filter(user=self.user, problem__title='Two Sum', course=self.course2).exists())
        self.assertEqual(UserProblemRecord.objects.filter(user=self.user, problem__title='Two Sum').count(), 2)

    def test_delete_problem_view(self):
        record1 = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course1
        )
        self.course1.problems.add(self.problem)
        
        record2 = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course2
        )
        self.course2.problems.add(self.problem)
        
        # Delete record1
        self.client.get(reverse('delete_problem', args=[record1.id]))
        
        # Verify record1 deleted, record2 exists
        self.assertFalse(UserProblemRecord.objects.filter(id=record1.id).exists())
        self.assertTrue(UserProblemRecord.objects.filter(id=record2.id).exists())
        
        # Verify problem removed from Course 1 but not Course 2
        self.assertFalse(self.course1.problems.filter(id=self.problem.id).exists())
        self.assertTrue(self.course2.problems.filter(id=self.problem.id).exists())

    def test_rename_course(self):
        response = self.client.post(reverse('edit_course', args=[self.course1.id]), {
            'name': 'Updated Course Name',
            'description': 'Updated Description',
            'language': 'cpp'
        })
        self.assertEqual(response.status_code, 302)
        self.course1.refresh_from_db()
        self.assertEqual(self.course1.name, 'Updated Course Name')
        self.assertEqual(self.course1.description, 'Updated Description')
        self.assertEqual(self.course1.language, 'cpp')

    def test_create_course(self):
        response = self.client.post(reverse('create_course'), {
            'name': 'New Course',
            'description': 'New Description',
            'language': 'cpp'
        })
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(name='New Course')
        self.assertEqual(course.language, 'cpp')

class LogsPageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.client = Client()
        self.client.login(username='user', password='password')
        
        self.course = Course.objects.create(user=self.user, name="Test Course")
        self.problem = Problem.objects.create(
            source='LC',
            source_id='test-problem',
            title='Test Problem',
            url='https://leetcode.com/problems/test-problem/',
            difficulty='Easy'
        )
        self.record = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course
        )
        
        from core.models import ReviewLog
        ReviewLog.objects.create(record=self.record, rating=2)
        ReviewLog.objects.create(record=self.record, rating=1)

    def test_logs_page_view(self):
        response = self.client.get(reverse('review_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/review_logs.html')
        self.assertEqual(len(response.context['logs']), 2)
        # Verify chronological order (newest first)
        self.assertEqual(response.context['logs'][0].rating, 1)
        self.assertEqual(response.context['logs'][1].rating, 2)
        self.assertEqual(response.context['latest_review'].rating, 1)

class DataManagementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.client = Client()
        self.client.login(username='user', password='password')
        
        self.course = Course.objects.create(user=self.user, name="Test Course")
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
            course=self.course,
            total_reviews=1
        )
        from core.models import ReviewLog
        ReviewLog.objects.create(record=self.record, rating=2)

    def test_export_data(self):
        response = self.client.get(reverse('export_data'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        import json
        data = json.loads(response.content)
        self.assertIn('problems', data)
        self.assertIn('courses', data)
        self.assertIn('records', data)
        self.assertIn('logs', data)
        
        self.assertEqual(len(data['problems']), 1)
        self.assertEqual(data['problems'][0]['fields']['title'], 'Test Prob')

    def test_import_data(self):
        # 1. Export current data
        export_response = self.client.get(reverse('export_data'))
        export_content = export_response.content
        
        # 2. Clear data (except user)
        UserProblemRecord.objects.all().delete()
        Course.objects.all().delete()
        Problem.objects.all().delete()
        
        # 3. Import data
        from io import BytesIO
        import_file = BytesIO(export_content)
        import_file.name = 'export.json'
        
        response = self.client.post(reverse('import_data'), {'file': import_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data imported successfully!')
        
        # 4. Verify data restored
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(Course.objects.count(), 1)
        self.assertEqual(UserProblemRecord.objects.count(), 1)
        self.assertEqual(UserProblemRecord.objects.first().total_reviews, 1)
        from core.models import ReviewLog
        self.assertEqual(ReviewLog.objects.count(), 1)

    def test_import_data_update(self):
        # 1. Export current data
        export_response = self.client.get(reverse('export_data'))
        export_content = export_response.content
        
        # 2. Modify local record (simulate older state)
        self.record.total_reviews = 0
        self.record.save()
        
        # 3. Import data (simulate newer state)
        from io import BytesIO
        import_file = BytesIO(export_content)
        import_file.name = 'export.json'
        
        response = self.client.post(reverse('import_data'), {'file': import_file})
        self.assertEqual(response.status_code, 200)
        
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_reviews, 1)

class ProblemDetailsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.client = Client()
        self.client.login(username='user', password='password')
        
        self.course = Course.objects.create(user=self.user, name="Test Course", language='python')
        self.problem = Problem.objects.create(
            source='LC',
            source_id='test-details',
            title='Test Details Problem',
            url='https://leetcode.com/problems/test-details/',
            difficulty='Medium',
            pattern_tags=['DP', 'Array']
        )
        self.record = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course,
            total_reviews=2,
            current_level=1
        )
        
        from core.models import ReviewLog
        ReviewLog.objects.create(record=self.record, rating=2)
        ReviewLog.objects.create(record=self.record, rating=1)

    def test_problem_details_view(self):
        response = self.client.get(reverse('problem_details', args=[self.problem.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/problem_details.html')
        
        # Verify context data
        self.assertEqual(response.context['problem'], self.problem)
        self.assertEqual(response.context['total_reviews'], 2)
        self.assertEqual(response.context['success_rate'], 50.0)
        self.assertEqual(len(response.context['logs']), 2)
        
        # Verify course stats
        stats = response.context['course_stats'][0]
        self.assertEqual(stats['course'], 'Test Course')
        self.assertEqual(stats['language'], 'Python')
        self.assertEqual(stats['total_reviews'], 2)
        self.assertEqual(stats['success_rate'], 50.0)

class UILinksTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='password')
        self.client = Client()
        self.client.login(username='user', password='password')
        
        self.course = Course.objects.create(user=self.user, name="Test Course")
        self.problem = Problem.objects.create(
            source='LC',
            source_id='test-link',
            title='Test Link Problem',
            url='https://leetcode.com/problems/test-link/',
            difficulty='Easy'
        )
        self.record = UserProblemRecord.objects.create(
            user=self.user,
            problem=self.problem,
            course=self.course,
            total_reviews=1
        )
        from core.models import ReviewLog
        ReviewLog.objects.create(record=self.record, rating=2)

    def test_links_present(self):
        # 1. All Problems
        response = self.client.get(reverse('all_problems'))
        self.assertContains(response, f'href="/problems/{self.problem.id}/"')
        
        # 2. Course Detail
        response = self.client.get(reverse('course_detail', args=[self.course.id]))
        self.assertContains(response, f'href="/problems/{self.problem.id}/"')
        
        # 3. Dashboard (Recent Activity)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, f'href="/problems/{self.problem.id}/"')
        
        # 4. Review Logs
        response = self.client.get(reverse('review_logs'))
        self.assertContains(response, f'href="/problems/{self.problem.id}/"')


