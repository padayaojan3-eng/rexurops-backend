from django.db import models

class Service(models.Model):
    SERVICE_TYPES = [
        ('fire_protection', 'Fire Protection'),
        ('fdas', 'FDAS / Fire Alarm'),
        ('wet_standpipe', 'Wet Standpipe'),
        ('fire_pump', 'Fire Pump'),
        ('cctv', 'CCTV'),
        ('intrusion', 'Intrusion'),
        ('lan_pabx', 'LAN / PABX'),
        ('automation', 'Automation'),
        ('solar', 'Solar'),
        ('electrical', 'Electrical'),
        ('motors', 'Motors'),
        ('wiring', 'Wiring'),
        ('mepf_works', 'MEPF Works'),
        ('water_pumps', 'Water Pumps'),
        ('compressor', 'Compressor'),
        ('water_tanks', 'Water Tanks'),
    ]

    name = models.CharField(max_length=50, choices=SERVICE_TYPES, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_name_display()