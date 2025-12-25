from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('queue/', views.review_queue, name='review_queue'),
    path('add/', views.add_problem, name='add_problem'),
    path('all/', views.all_problems, name='all_problems'),
    path('review/<int:record_id>/', views.log_review, name='log_review'),
]
