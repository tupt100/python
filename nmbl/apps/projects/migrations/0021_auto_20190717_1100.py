# Generated by Django 2.1.7 on 2019-07-17 11:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0020_merge_20190716_1103'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_attachment', to='projects.Project'),
        ),
        migrations.AddField(
            model_name='attachment',
            name='task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_attachment', to='projects.Task'),
        ),
        migrations.AddField(
            model_name='attachment',
            name='workflow',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_attachment', to='projects.Workflow'),
        ),
    ]
