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
