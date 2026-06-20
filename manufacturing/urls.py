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
    path('po/new/', views.po_new, name='po_new'),
    path('po/<int:po_id>/', views.po_detail, name='po_detail'),
    path('po/<int:po_id>/edit/', views.po_edit, name='po_edit'),
    path('po/<int:po_id>/items/add/', views.po_add_item, name='po_add_item'),
    path('po/<int:po_id>/items/remove/', views.po_remove_item,
         name='po_remove_item'),
    path('po/<int:po_id>/items/receive/', views.po_receive_item,
         name='po_receive_item'),
    path('po/<int:po_id>/status/', views.po_set_status, name='po_set_status'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('dept/<str:dept>/', views.generic_menu, name='dept_menu'),
    path('dept/<str:dept>/<path:subpath>/',
         views.generic_menu, name='submenu'),
    path(
    'run/<str:dept>/<path:subpath>/',
    views.run_script,
     name='run_script'),
]
