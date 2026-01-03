from django.contrib import admin
from .models import Problem, UserProblemRecord, ReviewLog, Course

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'source_id', 'difficulty')
    search_fields = ('title', 'source_id')
    list_filter = ('source', 'difficulty')

@admin.register(UserProblemRecord)
class UserProblemRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'problem', 'course', 'current_level', 'next_review_date', 'is_paused')
    list_filter = ('user', 'course', 'is_paused')
    search_fields = ('problem__title', 'user__username')

@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ('record', 'review_date', 'rating', 'time_spent')
    list_filter = ('rating', 'review_date')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'language', 'is_paused', 'created_at')
    list_filter = ('user', 'language', 'is_paused')
    search_fields = ('name',)
