from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('lecturer-dashboard/', views.lecturer_dashboard, name='lecturer_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Management URLs
    path('manage-lecturers/', views.manage_lecturers, name='manage_lecturers'),
    path('manage-programmes/', views.manage_programmes, name='manage_programmes'),
    path('manage-students/', views.manage_students, name='manage_students'),
    path('manage-units/', views.manage_units, name='manage_units'),
    path('manage-venues/', views.manage_venues, name='manage_venues'),
    path('manage-labs/', views.manage_labs, name='manage_labs'),
    path('lecturer-preferences/', views.lecturer_preferences, name='lecturer_preferences'),
    path('generate-timetable/', views.generate_timetable, name='generate_timetable'),
    path('view-timetables/', views.view_timetables, name='view_timetables'),
    path('manage-timeslots/', views.manage_timeslots, name='manage_timeslots'),
    path('room-availability/', views.room_availability, name='room_availability'),
]
