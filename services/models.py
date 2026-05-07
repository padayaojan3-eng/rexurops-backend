from django.db import models

class Service(models.Model):
    SERVICE_TYPES = [
        ('fire_protection', 'Fire Protection'),
        ('fdas', 'Fire Detection & Alarm System'),
        ('cctv', 'CCTV'),
        ('solar', 'Solar'),
        ('electrical', 'Electrical'),
        ('automation', 'Automation'),
        ('water_systems', 'Water Systems'),
    ]

    name = models.CharField(max_length=50, choices=SERVICE_TYPES, unique=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_name_display()