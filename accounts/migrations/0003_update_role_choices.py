from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_userprofile_specialization'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('mechanical_engineer', 'Mechanical Engineer'),
                    ('civil_engineer', 'Civil Engineer'),
                    ('architect', 'Architect'),
                    ('master_plumber', 'Master Plumber'),
                    ('worker', 'Worker'),
                    ('client', 'Client'),
                ],
                max_length=30,
            ),
        ),
    ]
