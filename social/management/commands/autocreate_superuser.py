from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Auto-create superuser from environment variables'

    def handle(self, *args, **kwargs):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'support10@idsolutionsindia.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Dinesh@7124')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Superuser "{username}" created!'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ Superuser "{username}" already exists.'))