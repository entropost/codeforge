from django.urls import path
from . import views

urlpatterns = [
    path('', views.review_queue, name='review_queue'),
    path('add/', views.add_problem, name='add_problem'),
    path('review/<int:record_id>/', views.log_review, name='log_review'),
]
