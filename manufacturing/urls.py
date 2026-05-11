from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout, name='logout'),
    path('register/', views.register, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/reset/', views.forgot_password_reset, name='forgot_password_reset'),
    path('change-password/', views.change_password, name='change_password'),
    path('user-roles/', views.user_roles, name='user_roles'),
    path('dept/<str:dept>/', views.dept_menu, name='dept_menu'),
    path('launch/<str:dept>/<str:subdept>/', views.launch_subdept, name='launch_subdept'),
]
