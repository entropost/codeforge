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
        # Placeholder for Codeforces implementation
        pass

class FSRSScheduler:
    def __init__(self):
        self.scheduler = Scheduler()

    def schedule(self, record, rating_val):
        """
        Updates the record's FSRS state based on the rating.
        rating_val: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
        """
        # Map integer rating to FSRS Rating enum
        rating_map = {
            1: Rating.Again,
            2: Rating.Hard,
            3: Rating.Good,
            4: Rating.Easy
        }
        rating = rating_map.get(rating_val)
        
        # Reconstruct Card
        # We infer state: New if 0 reviews, else Review (simplification)
        state = State.New if record.total_reviews == 0 else State.Review
        
        card = Card(
            state=state,
            stability=record.stability if record.total_reviews > 0 else None,
            difficulty=record.difficulty if record.total_reviews > 0 else None,
            last_review=record.last_review_date
        )
        
        # Perform review
        # review_card returns (Card, ReviewLog)
        # We need to handle the case where review_card expects a timezone-aware datetime
        now = datetime.now(timezone.utc)
        scheduled_card, review_log = self.scheduler.review_card(card, rating, review_datetime=now)
        
        # Update record
        record.stability = scheduled_card.stability
        record.difficulty = scheduled_card.difficulty
        record.last_review_date = scheduled_card.last_review
        record.next_review_date = scheduled_card.due
        
        return record

class FileManager:
    def __init__(self):
        self.base_path = Path(settings.BASE_REPO_PATH)

    def get_structured_path(self, problem):
        primary_tag = problem.pattern_tags[0] if problem.pattern_tags else "Uncategorized"
        # Sanitize tag
        safe_tag = "".join(c if c.isalnum() else "_" for c in primary_tag)
        difficulty_subdir = problem.difficulty.capitalize()
        return self.base_path / safe_tag / difficulty_subdir

    def create_solution_file(self, problem):
        dir_path = self.get_structured_path(problem)
        dir_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"{problem.source}_{problem.source_id}.py"
        file_path = dir_path / filename
        
        if not file_path.exists():
            content = f"# {problem.title}\n# {problem.url}\n# Difficulty: {problem.difficulty}\n# Tags: {', '.join(problem.pattern_tags)}\n\nclass Solution:\n    def solve(self):\n        pass\n"
            file_path.write_text(content)
            
        return str(file_path)
