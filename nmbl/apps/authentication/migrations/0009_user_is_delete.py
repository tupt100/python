# Generated by Django 2.1.7 on 2019-04-06 07:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_invitation_is_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_delete',
            field=models.BooleanField(default=False, verbose_name='Is Delete'),
        ),
    ]
