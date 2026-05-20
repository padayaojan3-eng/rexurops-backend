#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        username=os.environ.get('SUPERUSER_USERNAME', 'admin'),
        email=os.environ.get('SUPERUSER_EMAIL', ''),
        password=os.environ.get('SUPERUSER_PASSWORD', '')
    )
    print('Superuser created.')
else:
    print('Superuser already exists.')
"
