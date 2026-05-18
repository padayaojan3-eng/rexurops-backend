from django.db import migrations

SERVICES = [
    ('fire_protection', 'Fire Protection'),
    ('fdas',            'FDAS / Fire Alarm'),
    ('wet_standpipe',   'Wet Standpipe'),
    ('fire_pump',       'Fire Pump'),
    ('cctv',            'CCTV'),
    ('intrusion',       'Intrusion'),
    ('lan_pabx',        'LAN / PABX'),
    ('automation',      'Automation'),
    ('solar',           'Solar'),
    ('electrical',      'Electrical'),
    ('motors',          'Motors'),
    ('wiring',          'Wiring'),
    ('mepf_works',      'MEPF Works'),
    ('water_pumps',     'Water Pumps'),
    ('compressor',      'Compressor'),
    ('water_tanks',     'Water Tanks'),
]


def seed_services(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    for slug, label in SERVICES:
        Service.objects.get_or_create(name=slug, defaults={'description': label, 'is_active': True})


def remove_services(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    slugs = [s[0] for s in SERVICES]
    Service.objects.filter(name__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_alter_service_description_alter_service_name'),
    ]

    operations = [
        migrations.RunPython(seed_services, remove_services),
    ]
