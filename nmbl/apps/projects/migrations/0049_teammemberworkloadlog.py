# Generated by Django 2.1.7 on 2019-12-20 07:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0048_groupworkloadlog_group_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamMemberWorkLoadLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('category_type', models.CharField(blank=True, choices=[('project', 'Project'), ('workflow', 'Workflow'), ('task', 'Task')], max_length=225, null=True)),
                ('new', models.IntegerField(blank=True, default=0, null=True)),
                ('changed_at', models.DateField(blank=True, db_index=True, null=True)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_team_member_workload', to='projects.Project')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_team_member_workload', to='projects.Task')),
                ('team_member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='team_member_workload', to=settings.AUTH_USER_MODEL)),
                ('workflow', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_team_member_workload', to='projects.Workflow')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
