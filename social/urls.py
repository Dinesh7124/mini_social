from django.urls import path
from . import views

urlpatterns = [
    path('', views.feed, name='feed'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('settings/profile/', views.edit_profile, name='edit_profile'),
    path('notifications/', views.notifications, name='notifications'),
    path('search/', views.search, name='search'),
    path('api/reaction/<int:post_id>/', views.toggle_reaction, name='toggle_reaction'),
    # Messages / Chat
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    path('inbox/', views.inbox, name='inbox'),
    path('chat/<str:username>/', views.chat, name='chat'),
    path('api/message/<str:username>/send/', views.send_message, name='send_message'),
    path('api/message/<str:username>/new/', views.get_new_messages, name='get_new_messages'),

    # Stories
    path('stories/', views.stories_view, name='stories'),
    path('stories/create/', views.create_story, name='create_story'),

    # Saved Posts
    path('saved/', views.saved_posts, name='saved_posts'),
    path('api/save/<int:post_id>/', views.toggle_save, name='toggle_save'),

    # Suggestions + Live bell
    path('api/suggestions/', views.suggestions, name='suggestions'),
    path('api/unread/', views.unread_count, name='unread_count'),

    # Posts / Likes / Comments / Follow
    path('api/post/', views.create_post, name='create_post'),
    path('api/post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('api/post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('api/like/<int:post_id>/', views.toggle_like, name='toggle_like'),
    path('api/comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('api/follow/<str:username>/', views.toggle_follow, name='toggle_follow'),

    # Admin Panel
    path('panel/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/users/', views.admin_users, name='admin_users'),
    path('panel/users/<int:user_id>/role/', views.admin_change_role, name='admin_change_role'),
    path('panel/users/<int:user_id>/ban/', views.admin_toggle_ban, name='admin_toggle_ban'),
    path('panel/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('panel/posts/', views.admin_posts, name='admin_posts'),
    path('panel/posts/<int:post_id>/delete/', views.admin_delete_post, name='admin_delete_post'),
    path('panel/comments/', views.admin_comments, name='admin_comments'),
    path('panel/comments/<int:comment_id>/delete/', views.admin_delete_comment, name='admin_delete_comment'),
    path('panel/messages/', views.admin_messages, name='admin_messages'),
    path('panel/activity/', views.admin_activity, name='admin_activity'),
]