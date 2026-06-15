from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout, name='logout'),
    path('register/', views.register, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path(
    'forgot-password/reset/',
    views.forgot_password_reset,
     name='forgot_password_reset'),
    path('change-password/', views.change_password, name='change_password'),
    path('user-roles/', views.user_roles, name='user_roles'),
    path('po/', views.po_list, name='po_list'),
    path('po/<int:po_id>/', views.po_detail, name='po_detail'),
    path('dept/<str:dept>/', views.generic_menu, name='dept_menu'),
    path('dept/<str:dept>/<path:subpath>/',
         views.generic_menu, name='submenu'),
    path(
    'run/<str:dept>/<path:subpath>/',
    views.run_script,
     name='run_script'),
]
