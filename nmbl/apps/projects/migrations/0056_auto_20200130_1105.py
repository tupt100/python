# Generated by Django 2.1.7 on 2020-01-30 11:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0055_auto_20200109_1334'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='after_task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_after', to='projects.Task', verbose_name='After Task'),
        ),
        migrations.AddField(
            model_name='task',
            name='prior_task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_prior', to='projects.Task', verbose_name='Prior Task'),
        ),
    ]
