# Generated by Django 2.1.7 on 2019-08-05 19:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_group_is_public'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='user_avatar',
            field=models.ImageField(blank=True, null=True, upload_to='Profiles/%Y/%m/', verbose_name='Avatar'),
        ),
    ]
