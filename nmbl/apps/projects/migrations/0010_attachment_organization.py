# Generated by Django 2.1.7 on 2019-04-09 08:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0009_user_is_delete'),
        ('projects', '0009_task_pre_save_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attachment_organization', to='authentication.Organization', verbose_name='Company'),
        ),
    ]
