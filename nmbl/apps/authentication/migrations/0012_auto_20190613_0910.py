# Generated by Django 2.1.7 on 2019-06-13 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0008_notification_organization'),
        ('authentication', '0011_group_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='email_notification',
            field=models.ManyToManyField(related_name='user_email_notification', to='notifications.NotificationType'),
        ),
        migrations.AddField(
            model_name='invitation',
            name='in_app_notification',
            field=models.ManyToManyField(related_name='user_in_app_notification', to='notifications.NotificationType'),
        ),
    ]
