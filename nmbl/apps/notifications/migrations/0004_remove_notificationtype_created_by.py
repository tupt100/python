# Generated by Django 2.1.7 on 2019-04-06 07:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_auto_20190405_0627'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notificationtype',
            name='created_by',
        ),
    ]
