import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create or update superuser from environment variables'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('SUPERUSER_EMAIL', '')
        password = os.environ.get('SUPERUSER_PASSWORD', '')

        if not password:
            self.stdout.write(self.style.WARNING('SUPERUSER_PASSWORD not set, skipping.'))
            return

        user, created = User.objects.get_or_create(username=username)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" password updated.'))
