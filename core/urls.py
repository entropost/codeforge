from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('queue/', views.review_queue, name='review_queue'),
    path('add/', views.add_problem, name='add_problem'),
    path('add-manual/', views.add_problem_manual, name='add_problem_manual'),
    path('batch-add/', views.batch_add_problems, name='batch_add_problems'),
    path('all/', views.all_problems, name='all_problems'),
    path('review/<int:record_id>/', views.log_review, name='log_review'),
    path('problems/<int:problem_id>/', views.problem_details, name='problem_details'),
    path('reset/<int:record_id>/', views.reset_problem_progress, name='reset_progress'),
    path('delete/<int:record_id>/', views.delete_problem, name='delete_problem'),
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.create_course, name='create_course'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('courses/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    path('courses/<int:course_id>/delete/', views.delete_course, name='delete_course'),
    path('courses/<int:course_id>/import/', views.import_problems, name='import_problems'),
    path('toggle-pause/<int:record_id>/', views.toggle_problem_pause, name='toggle_problem_pause'),
    path('courses/<int:course_id>/toggle-pause/', views.toggle_course_pause, name='toggle_course_pause'),
    path('courses/<int:course_id>/reset/', views.reset_course_progress, name='reset_course_progress'),
    path('statistics/', views.statistics, name='statistics'),
    path('logs/', views.review_logs, name='review_logs'),
    path('data-management/', views.data_management, name='data_management'),
    path('export/', views.export_data, name='export_data'),
    path('import/', views.import_data, name='import_data'),
]
