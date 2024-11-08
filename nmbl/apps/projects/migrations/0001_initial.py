# Generated by Django 2.1.7 on 2019-03-25 09:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('document', models.FileField(blank=True, upload_to='Documents/')),
                ('object_id', models.PositiveIntegerField(blank=True, default=None, null=True)),
                ('content_type', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attachment_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PageInstruction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('instructions', models.TextField(blank=True, null=True, verbose_name='Instructions')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due Date')),
                ('importance', models.IntegerField(choices=[(1, 'High'), (2, 'Med'), (3, 'Low')], default=1, verbose_name='Project Priority')),
                ('instructions', models.TextField(blank=True, null=True, verbose_name='Instructions')),
                ('status', models.IntegerField(choices=[(1, 'Active'), (2, 'Completed'), (3, 'Archived')], default=1, verbose_name='Status')),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='project_assigned_by_user', to=settings.AUTH_USER_MODEL, verbose_name='Assigned By')),
                ('assigned_to_users', models.ManyToManyField(blank=True, related_name='project_assigned_to_users', to=settings.AUTH_USER_MODEL, verbose_name='Assigned To')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='project_organization', to='authentication.Organization', verbose_name='Company')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='project_owner', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due Date')),
                ('importance', models.IntegerField(choices=[(1, 'High'), (2, 'Med'), (3, 'Low')], default=1, verbose_name='Request Priority')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='request_assigned_by_user', to=settings.AUTH_USER_MODEL, verbose_name='Assigned By')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='request_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('request_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='request_by_user', to=settings.AUTH_USER_MODEL, verbose_name='Assigned To')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(max_length=254, verbose_name='Tag')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due Date')),
                ('importance', models.IntegerField(choices=[(1, 'High'), (2, 'Med'), (3, 'Low')], default=1, verbose_name='Task Priority')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('status', models.IntegerField(choices=[(1, 'New'), (2, 'In-Progress'), (3, 'Completed'), (4, 'Archived')], default=1, verbose_name='Status')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='task_assigned_to_user', to=settings.AUTH_USER_MODEL, verbose_name='Assigned To')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('observers', models.ManyToManyField(blank=True, related_name='task_observers', to=settings.AUTH_USER_MODEL, verbose_name='Observers')),
                ('task_tags', models.ManyToManyField(blank=True, related_name='task_tags', to='projects.Tag', verbose_name='Task Tag')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Workflow',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due Date')),
                ('importance', models.IntegerField(choices=[(1, 'High'), (2, 'Med'), (3, 'Low')], default=1, verbose_name='Workflow Priority')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('status', models.IntegerField(choices=[(1, 'Active'), (2, 'Completed'), (3, 'Archived')], default=1, verbose_name='Status')),
                ('assigned_to_users', models.ManyToManyField(blank=True, related_name='workflow_assigned_to_users', to=settings.AUTH_USER_MODEL, verbose_name='Assigned To')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_owner', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_assigned_project', to='projects.Project', verbose_name='Assigned Project')),
                ('workflow_tags', models.ManyToManyField(blank=True, related_name='workflow_tags', to='projects.Tag', verbose_name='Workflow Tag')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='task',
            name='workflow',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='task_workflow', to='projects.Workflow', verbose_name='Task Workflow'),
        ),
        migrations.AddField(
            model_name='project',
            name='project_tags',
            field=models.ManyToManyField(blank=True, related_name='project_tags', to='projects.Tag', verbose_name='Project Tag'),
        ),
    ]
