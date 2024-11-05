# Generated by Django 2.1.7 on 2019-12-23 04:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0050_tagchangelog_tag_reference'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompletionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('category_type', models.CharField(blank=True, choices=[('project', 'Project'), ('workflow', 'Workflow'), ('task', 'Task')], max_length=225, null=True)),
                ('completion_time', models.IntegerField(blank=True, default=0, null=True)),
                ('created_on', models.DateField(blank=True, db_index=True, null=True)),
                ('completed_on', models.DateField(blank=True, db_index=True, null=True)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_completion', to='projects.Project')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_completion', to='projects.Task')),
                ('team_member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='completed_by_team_member', to=settings.AUTH_USER_MODEL)),
                ('workflow', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_completion', to='projects.Workflow')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
