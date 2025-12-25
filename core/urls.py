from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('queue/', views.review_queue, name='review_queue'),
    path('add/', views.add_problem, name='add_problem'),
    path('batch-add/', views.batch_add_problems, name='batch_add_problems'),
    path('all/', views.all_problems, name='all_problems'),
    path('review/<int:record_id>/', views.log_review, name='log_review'),
    path('reset/<int:record_id>/', views.reset_problem_progress, name='reset_progress'),
    path('delete/<int:record_id>/', views.delete_problem, name='delete_problem'),
]
