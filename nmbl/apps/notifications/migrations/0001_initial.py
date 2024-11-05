# Generated by Django 2.1.7 on 2019-03-27 06:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('status', models.IntegerField(choices=[(1, 'Unread'), (2, 'Read')], default=1, verbose_name='Status')),
                ('is_notify', models.BooleanField(default=False, verbose_name='Notified')),
                ('title', models.CharField(db_index=True, max_length=254, verbose_name='Title')),
                ('notification_type', models.IntegerField(choices=[(1, 'New Project'), (2, 'New Workflow')], default=1, verbose_name='Notification Type')),
                ('message_body', models.TextField(null=True, verbose_name='Message Content')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notification_user', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='NotificationType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Notification Name')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_type_user', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='OutgoingEmailTemplates',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Email Template Name')),
                ('subject', models.CharField(max_length=254)),
                ('message', models.TextField(help_text='You can move or duplicate {} bracket words, but you CANNOT edit or change the words inside.')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='UserNotificationSetting',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('in_app_notification', models.BooleanField(default=False, verbose_name='In App Notification')),
                ('email_notification', models.BooleanField(default=False, verbose_name='Email Notification')),
                ('notification_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_type_setting', to='notifications.NotificationType')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_setting_user', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='usernotificationsetting',
            unique_together={('in_app_notification', 'email_notification', 'user', 'notification_type')},
        ),
        migrations.AlterUniqueTogether(
            name='notificationtype',
            unique_together={('name', 'created_by')},
        ),
    ]
