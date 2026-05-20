from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('mechanical_engineer', 'Mechanical Engineer'),
        ('civil_engineer', 'Civil Engineer'),
        ('architect', 'Architect'),
        ('master_plumber', 'Master Plumber'),
        ('worker', 'Worker'),
        ('client', 'Client'),
    ]

    ENGINEER_ROLES = ['mechanical_engineer', 'civil_engineer', 'architect']
    WORKER_ROLES = ['master_plumber', 'worker']

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    specialization = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"