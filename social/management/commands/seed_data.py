from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from social.models import Post, Comment, Follow, Like, Reaction


class Command(BaseCommand):
    help = 'Seed database with sample data'

    def handle(self, *args, **kwargs):
        # Create users
        users = []
        sample_users = [
            ('alice', 'alice@test.com', 'Alice', 'Smith', '9876543211'),
            ('bob', 'bob@test.com', 'Bob', 'Johnson', '9876543212'),
            ('charlie', 'charlie@test.com', 'Charlie', 'Brown', '9876543213'),
        ]

        for username, email, first, last, phone in sample_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                }
            )
            if created:
                user.set_password('test1234')
                user.save()
                user.profile.phone_number = phone
                user.profile.save()
                self.stdout.write(self.style.SUCCESS(f'✅ User: {username}'))

            users.append(user)

        # Create posts
        posts_data = [
            (users[0], 'Hello world! My first post 🎉'),
            (users[1], 'Great platform!'),
            (users[2], 'Anyone up for chat? #hello'),
        ]

        for author, content in posts_data:
            post, created = Post.objects.get_or_create(
                author=author, content=content
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Post by {author.username}'))

        # Create follows
        follows = [
            (users[0], users[1]),
            (users[0], users[2]),
            (users[1], users[0]),
        ]

        for follower, following in follows:
            Follow.objects.get_or_create(
                follower=follower, following=following
            )

        self.stdout.write(self.style.SUCCESS('✅ Data seeded successfully!'))