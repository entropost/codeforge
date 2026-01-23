import os
import requests
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from fsrs import Scheduler, Card, Rating, State

class ProblemFetcher:
    @staticmethod
    def fetch_leetcode(url):
        """
        Fetches problem details from LeetCode using GraphQL.
        """
        slug = url.rstrip('/').split('/')[-1]
        query = """
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                title
                difficulty
                topicTags {
                    name
                }
            }
        }
        """
        response = requests.post(
            'https://leetcode.com/graphql',
            json={'query': query, 'variables': {'titleSlug': slug}},
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch from LeetCode: {response.status_code}")
            
        data = response.json()['data']['question']
        if not data:
             raise Exception("Problem not found or invalid URL")

        return {
            'source': 'LC',
            'source_id': slug,
            'title': data['title'],
            'url': url,
            'difficulty': data['difficulty'],
            'pattern_tags': [tag['name'] for tag in data['topicTags']]
        }

    @staticmethod
    def fetch_codeforces(url):
        """
        Fetches problem details from Codeforces using the official API.
        Handles both /problemset/problem/ and /contest/X/problem/Y formats.
        """
        # Extract contestId and index
        parts = url.rstrip('/').split('/')
        if 'problemset/problem' in url:
            # https://codeforces.com/problemset/problem/2051/D
            contest_id = parts[-2]
            index = parts[-1]
        elif 'contest' in url and 'problem' in url:
            # https://codeforces.com/contest/2051/problem/D
            contest_id = parts[-3]
            index = parts[-1]
        else:
            raise Exception("Unsupported Codeforces URL format. Use /problemset/problem/X/Y or /contest/X/problem/Y")

        api_url = "https://codeforces.com/api/problemset.problems"
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch from Codeforces API: {response.status_code}")
                
            data = response.json()
            if data['status'] != 'OK':
                raise Exception(f"Codeforces API error: {data.get('comment')}")
                
            problems = data['result']['problems']
            target_problem = None
            for p in problems:
                if str(p.get('contestId')) == str(contest_id) and p.get('index') == index:
                    target_problem = p
                    break
            
            if not target_problem:
                raise Exception(f"Problem {contest_id}{index} not found in Codeforces API")
                
            return {
                'source': 'CF',
                'source_id': f"{contest_id}{index}",
                'title': target_problem['name'],
                'url': url,
                'difficulty': str(target_problem.get('rating', 'Medium')),
                'pattern_tags': target_problem.get('tags', [])
            }
        except requests.RequestException as e:
            raise Exception(f"Network error while fetching from Codeforces: {e}")

    @staticmethod
    def fetch_cses(url):
        """
        Fetches problem details from CSES.
        """
        # https://cses.fi/problemset/task/1068
        try:
            task_id = url.rstrip('/').split('/')[-1]
            if not task_id.isdigit():
                 # Try second to last if trailing slash
                task_id = url.rstrip('/').split('/')[-2]
                
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch from CSES: {response.status_code}")
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_tag = soup.find('h1')
            if not title_tag:
                 raise Exception("Could not find title on CSES page")
            
            title = title_tag.text.strip()
            
            # CSES doesn't have tags on the problem page usually, but we can try to find the section
            # For now, we'll leave tags empty or maybe infer from the previous page if we crawled
            
            return {
                'source': 'CS',
                'source_id': task_id,
                'title': title,
                'url': url,
                'difficulty': 'Medium', # Default
                'pattern_tags': []
            }

        except Exception as e:
             raise Exception(f"Error fetching CSES problem: {e}")

class LevelScheduler:
    def schedule(self, record, rating_val):
        """
        Updates the record's next review date based on a binary Pass/Fail rating.
        rating_val: 1 (Fail), 2 (Pass)
        """
        from django.conf import settings
        intervals = settings.REVIEW_INTERVALS
        now = timezone.now()

        if rating_val == 2:  # Pass
            # Increment level, but don't exceed the number of defined intervals
            record.current_level = min(record.current_level + 1, len(intervals))
            
            # Level 1 uses intervals[0], Level 2 uses intervals[1], etc.
            # If level is 0 (shouldn't happen on pass if we increment first), default to 1 day
            days = intervals[record.current_level - 1] if record.current_level > 0 else 1
            record.next_review_date = now + timedelta(days=days)
        else:  # Fail
            record.current_level = 0
            record.next_review_date = now + timedelta(days=1)

        record.last_review_date = now
        return record

class PracticeFileManager:
    @staticmethod
    def create_practice_file(record):
        """
        Creates a practice file for the given record.
        Path: <PRACTICE_DIRECTORY>/<course_name>/level <level>/<problem_title>.<ext>
        """
        if not getattr(settings, 'ENABLE_PRACTICE_REPO', True) or not settings.PRACTICE_DIRECTORY:
            return None

        import re
        def sanitize(text):
            return re.sub(r'[\\/*?:"<>|]', "", text).replace(" ", "_")

        base_path = Path(settings.PRACTICE_DIRECTORY)
        course_name = record.course.name if record.course else "General"
        course_dir = base_path / sanitize(course_name)
        level_dir = course_dir / f"level_{record.current_level}"
        
        # Determine extension
        ext = 'py'
        if record.course and record.course.language == 'cpp':
            ext = 'cpp'
        
        # Sanitize problem title for filename
        filename = f"{sanitize(record.problem.title)}.{ext}"
        file_path = level_dir / filename

        try:
            # Create directories
            level_dir.mkdir(parents=True, exist_ok=True)
            
            # Create file if it doesn't exist
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    if ext == 'py':
                        f.write(f"# Problem: {record.problem.title}\n")
                        f.write(f"# URL: {record.problem.url}\n\n")
                    else:
                        f.write(f"// Problem: {record.problem.title}\n")
                        f.write(f"// URL: {record.problem.url}\n\n")
                        f.write("#include <iostream>\n\nusing namespace std;\n\nint main() {\n    return 0;\n}\n")
            
            return str(file_path)
        except Exception as e:
            print(f"Error creating practice file: {e}")
            return None

class GitManager:
    @staticmethod
    def commit_review(file_path, status, course_name, problem_title, level):
        """
        Adds and commits the practice file to git.
        """
        if not getattr(settings, 'ENABLE_PRACTICE_REPO', True):
            return

        if not file_path or not os.path.exists(file_path):
            return
        
        import subprocess
        try:
            # Get the directory of the file to run git commands in
            file_dir = os.path.dirname(file_path)
            
            # Check if there are changes to the file
            # git status --porcelain <file_path> returns empty if no changes
            status_proc = subprocess.run(
                ['git', 'status', '--porcelain', file_path], 
                cwd=file_dir, 
                capture_output=True, 
                text=True
            )
            
            # If no changes and file is already tracked, status_proc.stdout will be empty.
            # However, we might want to commit anyway if it's a new file (untracked).
            # Untracked files show up as ?? in porcelain.
            
            if not status_proc.stdout.strip():
                # No changes to commit
                return

            # git add
            subprocess.run(['git', 'add', file_path], cwd=file_dir, check=True)
            
            # git commit - only this file
            message = f"{status} | Course: {course_name} | Problem: {problem_title} | Level: {level}"
            subprocess.run(['git', 'commit', '-m', message, file_path], cwd=file_dir, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Git error: {e}")
        except Exception as e:
            print(f"Unexpected error during git commit: {e}")
