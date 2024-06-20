# Generated by Django 5.0.6 on 2024-06-19 14:12

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatapp', '0004_alter_group_admins_alter_group_members'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='admins',
            field=models.ManyToManyField(blank=True, related_name='admin_groups', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='group',
            name='members',
            field=models.ManyToManyField(blank=True, related_name='member_groups', to=settings.AUTH_USER_MODEL),
        ),
    ]
