# ============ IMPORTS ============
import os
import random
import resend
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings

from .models import (
    Post, Comment, Like, Follow, Notification,
    Message, Story, SavedPost, Reaction, Profile,
    PasswordResetOTP
)


# ============ RESEND CONFIG ============
resend.api_key = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = 'MiniSocial <onboarding@resend.dev>'  # Resend default testing domain


# ============ EMAIL HELPER ============
def send_email_via_resend(to_email, subject, html_body, text_body=None):
    """Send email via Resend HTTP API (works on Render free tier)."""
    if not resend.api_key:
        print(f'⚠️ RESEND_API_KEY not set. Skipping email to {to_email}')
        print(f'Subject: {subject}')
        print(f'Body: {html_body[:200]}...')
        return False

    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        print(f'✅ Email sent to {to_email}')
        return True
    except Exception as e:
        print(f'❌ Email send failed: {e}')
        return False


# ============ REACTION HELPERS ============
def _get_reaction_counts(post):
    """Helper: count reactions by type for a post."""
    counts = {}
    for row in Reaction.objects.filter(post=post).values('reaction_type').annotate(count=Count('id')):
        counts[row['reaction_type']] = row['count']
    return counts


# ============ AUTH ============
def login_view(request):
    if request.user.is_authenticated:
        return redirect('feed')

    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = None
        if '@' in username_or_email:
            u = User.objects.filter(email__iexact=username_or_email).first()
            if u:
                user = authenticate(request, username=u.username, password=password)
        else:
            user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            if user.profile.is_banned:
                return render(request, 'social/login.html', {
                    'error': f'Your account is banned. Reason: {user.profile.ban_reason}'
                })
            login(request, user)
            next_url = request.GET.get('next', 'feed')
            return redirect(next_url)
        else:
            return render(request, 'social/login.html', {
                'error': 'Invalid username/email or password.',
            })

    return render(request, 'social/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('feed')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not email:
            errors.append('Email is required.')
        if not phone:
            errors.append('Phone number is required.')
        if not password:
            errors.append('Password is required.')
        if password != password2:
            errors.append('Passwords do not match.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if email and User.objects.filter(email__iexact=email).exists():
            errors.append('This email is already registered.')
        if phone and Profile.objects.filter(phone_number=phone).exists():
            errors.append('This phone number is already registered.')

        if errors:
            return render(request, 'social/login.html', {
                'error': ' | '.join(errors),
                'show_register': True,
                'form_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                }
            })

        # Auto-generate username
        base_username = first_name.lower().replace(' ', '')
        username = base_username + str(random.randint(1000, 9999))
        while User.objects.filter(username=username).exists():
            username = base_username + str(random.randint(1000, 9999))

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        user.profile.phone_number = phone
        user.profile.save()

        # Send welcome email via Resend
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#6366f1;">Welcome to MiniSocial, {first_name}! 🎉</h2>
            <p>Your account has been created successfully.</p>
            <div style="background:#f4f6f9;padding:15px;border-radius:8px;margin:20px 0;">
                <h3 style="margin-top:0;">Your Login Details</h3>
                <p><strong>Username:</strong> {username}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Password:</strong> (the one you set)</p>
            </div>
            <p>You can log in using either your username or email.</p>
            <p>Happy connecting!<br><strong>MiniSocial Team</strong></p>
        </div>
        """
        send_email_via_resend(
            to_email=email,
            subject='Welcome to MiniSocial — Your Account Details',
            html_body=html_body,
        )

        login(request, user)
        return redirect('feed')

    return render(request, 'social/login.html', {'show_register': True})


def logout_view(request):
    logout(request)
    return redirect('login')


# ============ FORGOT PASSWORD (3 Steps) ============
def forgot_password_view(request):
    """Step 1: User enters email/phone"""
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()

        user = None
        if '@' in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            profile = Profile.objects.filter(phone_number=identifier).first()
            if profile:
                user = profile.user

        if not user:
            return render(request, 'social/forgot_password.html', {
                'error': 'No account found with this email/phone.'
            })

        otp_code = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
        PasswordResetOTP.objects.create(user=user, otp=otp_code)

        # Send OTP via Resend
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#6366f1;">Password Reset OTP</h2>
            <p>Hi {user.first_name or user.username},</p>
            <p>You requested to reset your password.</p>
            <div style="background:#f4f6f9;padding:20px;border-radius:8px;margin:20px 0;text-align:center;">
                <p style="margin:0;font-size:14px;color:#6b7280;">Your OTP is:</p>
                <h1 style="font-size:36px;letter-spacing:8px;color:#6366f1;margin:10px 0;">{otp_code}</h1>
            </div>
            <p>This OTP is valid for <strong>10 minutes</strong>.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <p>MiniSocial Team</p>
        </div>
        """
        send_email_via_resend(
            to_email=user.email,
            subject='MiniSocial — Password Reset OTP',
            html_body=html_body,
        )

        return render(request, 'social/forgot_password.html', {
            'step': 'verify',
            'identifier': identifier,
            'dev_otp': otp_code if settings.DEBUG else None,
            'info': f'OTP sent to {user.email}. Check your inbox.'
        })

    return render(request, 'social/forgot_password.html')


def verify_otp_view(request):
    """Step 2: User enters OTP"""
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        otp_entered = request.POST.get('otp', '').strip()

        user = None
        if '@' in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            profile = Profile.objects.filter(phone_number=identifier).first()
            if profile:
                user = profile.user

        if not user:
            return render(request, 'social/forgot_password.html', {
                'error': 'User not found. Please try again.'
            })

        otp_record = PasswordResetOTP.objects.filter(
            user=user, otp=otp_entered, is_used=False
        ).order_by('-created_at').first()

        if not otp_record or otp_record.is_expired():
            return render(request, 'social/forgot_password.html', {
                'step': 'verify',
                'identifier': identifier,
                'error': 'Invalid or expired OTP. Please try again.'
            })

        otp_record.is_used = True
        otp_record.save()

        return render(request, 'social/forgot_password.html', {
            'step': 'reset',
            'identifier': identifier,
            'info': 'OTP verified! Set your new password.'
        })

    return redirect('forgot_password')


def reset_password_view(request):
    """Step 3: User sets new password"""
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if new_password != confirm_password:
            return render(request, 'social/forgot_password.html', {
                'step': 'reset',
                'identifier': identifier,
                'error': 'Passwords do not match.'
            })

        if len(new_password) < 6:
            return render(request, 'social/forgot_password.html', {
                'step': 'reset',
                'identifier': identifier,
                'error': 'Password must be at least 6 characters.'
            })

        user = None
        if '@' in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            profile = Profile.objects.filter(phone_number=identifier).first()
            if profile:
                user = profile.user

        if user:
            user.set_password(new_password)
            user.save()
            return render(request, 'social/login.html', {
                'info': 'Password reset successful! Please login with your new password.'
            })

    return redirect('forgot_password')


# ============ FEED ============
@login_required
def feed(request):
    following_ids = list(request.user.following.values_list('following_id', flat=True))
    posts_list = Post.objects.filter(
        Q(author__in=following_ids) | Q(author=request.user)
    ).select_related('author').prefetch_related(
        'comments__author', 'comments__replies__author', 'likes'
    )

    paginator = Paginator(posts_list, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    liked_ids = set(request.user.likes.values_list('post_id', flat=True))
    saved_ids = set(request.user.saved_posts.values_list('post_id', flat=True))
    unread_count = request.user.notifications.filter(is_read=False).count()

    cutoff = timezone.now() - timedelta(hours=24)
    active_stories = Story.objects.filter(
        created_at__gte=cutoff
    ).select_related('author').order_by('-created_at')[:20]

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('social/_post_list.html', {
            'posts': page_obj,
            'liked_ids': liked_ids,
            'saved_ids': saved_ids,
        }, request=request)
        return JsonResponse({
            'html': html,
            'has_next': page_obj.has_next(),
        })

    return render(request, 'social/feed.html', {
        'posts': page_obj,
        'liked_ids': liked_ids,
        'saved_ids': saved_ids,
        'unread_count': unread_count,
        'active_stories': active_stories,
        'has_next': page_obj.has_next(),
    })


# ============ PROFILE ============
@login_required
def profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    posts = user_obj.posts.all()

    is_own = (request.user == user_obj)

    if is_own:
        is_following = False
    else:
        is_following = Follow.objects.filter(
            follower=request.user, following=user_obj
        ).exists()

    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/profile.html', {
        'profile_user': user_obj,
        'posts': posts,
        'is_following': is_following,
        'is_own': is_own,
        'unread_count': unread_count,
    })


@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '').strip()
        profile.location = request.POST.get('location', '').strip()

        website = request.POST.get('website', '').strip()
        if website and not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        profile.website = website

        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        if request.FILES.get('cover'):
            profile.cover = request.FILES['cover']
        profile.save()
        return redirect('profile', username=request.user.username)

    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/edit_profile.html', {
        'profile': profile,
        'unread_count': unread_count
    })


# ============ POSTS ============
@login_required
@require_POST
def create_post(request):
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')
    video = request.FILES.get('video')
    if content or image or video:
        Post.objects.create(
            author=request.user,
            content=content,
            image=image,
            video=video
        )
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Empty post'}, status=400)


@login_required
@require_POST
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    content = request.POST.get('content', '').strip()
    if content:
        post.content = content
        post.save()
        return JsonResponse({'success': True, 'content': post.content})
    return JsonResponse({'error': 'Empty content'}, status=400)


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    return JsonResponse({'success': True})


# ============ LIKE ============
@login_required
@require_POST
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
        return JsonResponse({'liked': False, 'count': post.likes_count})

    if post.author != request.user:
        Notification.objects.create(
            recipient=post.author, sender=request.user,
            notif_type='like', post=post
        )
    return JsonResponse({'liked': True, 'count': post.likes_count})


# ============ REACTION ============
@login_required
@require_POST
def toggle_reaction(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    reaction_type = request.POST.get('reaction', 'like')

    if reaction_type not in ['like', 'love', 'haha', 'wow', 'sad', 'angry']:
        reaction_type = 'like'

    existing = Reaction.objects.filter(user=request.user, post=post).first()

    if existing:
        if existing.reaction_type == reaction_type:
            existing.delete()
            return JsonResponse({
                'removed': True,
                'reaction': None,
                'counts': _get_reaction_counts(post),
            })
        else:
            existing.reaction_type = reaction_type
            existing.save()
            return JsonResponse({
                'removed': False,
                'reaction': reaction_type,
                'counts': _get_reaction_counts(post),
            })
    else:
        Reaction.objects.create(user=request.user, post=post, reaction_type=reaction_type)

        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author, sender=request.user,
                notif_type='like', post=post
            )

        return JsonResponse({
            'removed': False,
            'reaction': reaction_type,
            'counts': _get_reaction_counts(post),
        })


# ============ COMMENT ============
@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '').strip()
    parent_id = request.POST.get('parent_id')
    parent = Comment.objects.filter(id=parent_id).first() if parent_id else None
    if content:
        comment = Comment.objects.create(
            post=post, author=request.user,
            content=content, parent=parent
        )
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author, sender=request.user,
                notif_type='comment', post=post
            )
        return JsonResponse({
            'id': comment.id,
            'content': comment.content,
            'author': comment.author.username,
            'parent_id': parent_id,
        })
    return JsonResponse({'error': 'Empty'}, status=400)


# ============ FOLLOW ============
@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

    follow, created = Follow.objects.get_or_create(
        follower=request.user, following=target
    )
    if not created:
        follow.delete()
        return JsonResponse({'following': False, 'followers_count': target.profile.followers_count})

    Notification.objects.create(
        recipient=target, sender=request.user, notif_type='follow'
    )
    return JsonResponse({'following': True, 'followers_count': target.profile.followers_count})


# ============ NOTIFICATIONS ============
@login_required
def notifications(request):
    notifs = request.user.notifications.select_related('sender', 'post')[:50]
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'social/notifications.html', {'notifications': notifs})


@login_required
def unread_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})


# ============ SEARCH ============
def search(request):
    query = request.GET.get('q', '').strip()
    users, posts = [], []
    if query:
        users = User.objects.filter(username__icontains=query)[:20]
        posts = Post.objects.filter(content__icontains=query)[:20]
    unread_count = request.user.notifications.filter(is_read=False).count() if request.user.is_authenticated else 0
    return render(request, 'social/search.html', {
        'query': query, 'users': users, 'posts': posts, 'unread_count': unread_count
    })


# ============ MESSAGES / CHAT ============
@login_required
def inbox(request):
    sent = Message.objects.filter(sender=request.user).values_list('recipient', flat=True)
    received = Message.objects.filter(recipient=request.user).values_list('sender', flat=True)
    user_ids = set(list(sent) + list(received))

    conversations = []
    for uid in user_ids:
        other = User.objects.get(id=uid)
        last_msg = Message.objects.filter(
            Q(sender=request.user, recipient=other) |
            Q(sender=other, recipient=request.user)
        ).order_by('-created_at').first()
        unread = Message.objects.filter(sender=other, recipient=request.user, is_read=False).count()
        conversations.append({
            'user': other,
            'last_message': last_msg,
            'unread': unread,
        })

    conversations.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else timezone.now(),
        reverse=True
    )
    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/inbox.html', {
        'conversations': conversations,
        'unread_count': unread_count,
    })


@login_required
def chat(request, username):
    other = get_object_or_404(User, username=username)
    if other == request.user:
        return redirect('inbox')

    messages = Message.objects.filter(
        Q(sender=request.user, recipient=other) |
        Q(sender=other, recipient=request.user)
    ).order_by('created_at')

    Message.objects.filter(sender=other, recipient=request.user, is_read=False).update(is_read=True)

    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/chat.html', {
        'other': other,
        'messages': messages,
        'unread_count': unread_count,
    })


@login_required
@require_POST
def send_message(request, username):
    other = get_object_or_404(User, username=username)
    content = request.POST.get('content', '').strip()
    if content:
        msg = Message.objects.create(sender=request.user, recipient=other, content=content)
        return JsonResponse({
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.username,
            'created_at': msg.created_at.strftime('%H:%M'),
        })
    return JsonResponse({'error': 'Empty'}, status=400)


@login_required
def get_new_messages(request, username):
    other = get_object_or_404(User, username=username)
    last_id = int(request.GET.get('last_id', 0))
    new_msgs = Message.objects.filter(
        Q(sender=request.user, recipient=other) |
        Q(sender=other, recipient=request.user),
        id__gt=last_id
    ).order_by('created_at')

    Message.objects.filter(sender=other, recipient=request.user, is_read=False).update(is_read=True)

    return JsonResponse({
        'messages': [
            {
                'id': m.id,
                'content': m.content,
                'sender': m.sender.username,
                'is_mine': m.sender == request.user,
                'created_at': m.created_at.strftime('%H:%M'),
            }
            for m in new_msgs
        ]
    })


# ============ STORIES ============
@login_required
def create_story(request):
    if request.method == 'POST' and request.FILES.get('image'):
        Story.objects.create(
            author=request.user,
            image=request.FILES['image'],
            caption=request.POST.get('caption', '').strip()
        )
        return redirect('feed')
    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/create_story.html', {'unread_count': unread_count})


@login_required
def stories_view(request):
    cutoff = timezone.now() - timedelta(hours=24)
    stories = Story.objects.filter(created_at__gte=cutoff).select_related('author').order_by('-created_at')
    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/stories.html', {
        'stories': stories,
        'unread_count': unread_count,
    })


# ============ SAVED POSTS ============
@login_required
@require_POST
def toggle_save(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    saved, created = SavedPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        saved.delete()
        return JsonResponse({'saved': False})
    return JsonResponse({'saved': True})


@login_required
def saved_posts(request):
    saved = request.user.saved_posts.select_related('post__author')
    unread_count = request.user.notifications.filter(is_read=False).count()
    return render(request, 'social/saved.html', {
        'saved': saved,
        'unread_count': unread_count,
    })


# ============ SUGGESTIONS ============
@login_required
def suggestions(request):
    following_ids = list(request.user.following.values_list('following_id', flat=True))
    following_ids.append(request.user.id)

    users = User.objects.exclude(
        id__in=following_ids
    ).order_by('-date_joined')[:5]

    return JsonResponse({
        'users': [
            {
                'username': u.username,
                'avatar': u.profile.avatar.url if u.profile.avatar else None,
                'followers': u.profile.followers_count,
            }
            for u in users
        ]
    })


# ============ ADMIN HELPERS ============
def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.profile.role == 'admin')


def is_moderator(user):
    return user.is_authenticated and (user.is_superuser or user.profile.role in ['moderator', 'admin'])


# ============ ADMIN DASHBOARD ============
@login_required
@user_passes_test(is_admin, login_url='/')
def admin_dashboard(request):
    total_users = User.objects.count()
    total_posts = Post.objects.count()
    total_comments = Comment.objects.count()
    total_messages = Message.objects.count()
    total_stories = Story.objects.count()

    week_ago = timezone.now() - timedelta(days=7)
    new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
    new_posts_week = Post.objects.filter(created_at__gte=week_ago).count()

    top_users = User.objects.annotate(post_count=Count('posts')).order_by('-post_count')[:5]
    recent_users = User.objects.order_by('-date_joined')[:10]
    recent_posts = Post.objects.select_related('author').order_by('-created_at')[:10]

    return render(request, 'social/admin_dashboard.html', {
        'total_users': total_users,
        'total_posts': total_posts,
        'total_comments': total_comments,
        'total_messages': total_messages,
        'total_stories': total_stories,
        'new_users_week': new_users_week,
        'new_posts_week': new_posts_week,
        'top_users': top_users,
        'recent_users': recent_users,
        'recent_posts': recent_posts,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


# ============ MANAGE USERS ============
@login_required
@user_passes_test(is_admin, login_url='/')
def admin_users(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    users = User.objects.select_related('profile').order_by('-date_joined')

    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if role_filter:
        users = users.filter(profile__role=role_filter)
    if status_filter == 'banned':
        users = users.filter(profile__is_banned=True)
    elif status_filter == 'active':
        users = users.filter(profile__is_banned=False)

    return render(request, 'social/admin_users.html', {
        'users': users,
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


@login_required
@user_passes_test(is_admin, login_url='/')
@require_POST
def admin_change_role(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot change your own role'}, status=400)
    if target.is_superuser:
        return JsonResponse({'error': 'Cannot change superuser'}, status=400)

    new_role = request.POST.get('role', 'user')
    if new_role not in ['user', 'moderator', 'admin']:
        return JsonResponse({'error': 'Invalid role'}, status=400)

    target.profile.role = new_role
    target.profile.save()
    target.is_staff = (new_role == 'admin')
    target.save()

    return JsonResponse({'success': True, 'role': new_role})


@login_required
@user_passes_test(is_admin, login_url='/')
@require_POST
def admin_toggle_ban(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot ban yourself'}, status=400)
    if target.is_superuser:
        return JsonResponse({'error': 'Cannot ban superuser'}, status=400)

    target.profile.is_banned = not target.profile.is_banned
    if target.profile.is_banned:
        target.profile.ban_reason = request.POST.get('reason', '').strip()
    else:
        target.profile.ban_reason = ''
    target.profile.save()

    return JsonResponse({
        'success': True,
        'banned': target.profile.is_banned,
    })


@login_required
@user_passes_test(is_admin, login_url='/')
@require_POST
def admin_delete_user(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot delete yourself'}, status=400)
    if target.is_superuser:
        return JsonResponse({'error': 'Cannot delete superuser'}, status=400)

    username = target.username
    target.delete()
    return JsonResponse({'success': True, 'username': username})


# ============ MANAGE POSTS ============
@login_required
@user_passes_test(is_moderator, login_url='/')
def admin_posts(request):
    query = request.GET.get('q', '').strip()
    posts = Post.objects.select_related('author').order_by('-created_at')
    if query:
        posts = posts.filter(Q(content__icontains=query) | Q(author__username__icontains=query))

    return render(request, 'social/admin_posts.html', {
        'posts': posts[:100],
        'query': query,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


@login_required
@user_passes_test(is_moderator, login_url='/')
@require_POST
def admin_delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    return JsonResponse({'success': True})


# ============ MANAGE COMMENTS ============
@login_required
@user_passes_test(is_moderator, login_url='/')
def admin_comments(request):
    comments = Comment.objects.select_related('author', 'post__author').order_by('-created_at')[:200]
    return render(request, 'social/admin_comments.html', {
        'comments': comments,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


@login_required
@user_passes_test(is_moderator, login_url='/')
@require_POST
def admin_delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    comment.delete()
    return JsonResponse({'success': True})


# ============ MONITOR MESSAGES ============
@login_required
@user_passes_test(is_admin, login_url='/')
def admin_messages(request):
    messages = Message.objects.select_related('sender', 'recipient').order_by('-created_at')[:100]
    return render(request, 'social/admin_messages.html', {
        'messages': messages,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


# ============ ACTIVITY LOG ============
@login_required
@user_passes_test(is_admin, login_url='/')
def admin_activity(request):
    recent_follows = Follow.objects.select_related('follower', 'following').order_by('-created_at')[:20]
    recent_likes = Like.objects.select_related('user', 'post__author').order_by('-created_at')[:20]

    return render(request, 'social/admin_activity.html', {
        'recent_follows': recent_follows,
        'recent_likes': recent_likes,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })