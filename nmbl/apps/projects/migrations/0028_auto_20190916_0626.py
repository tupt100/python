# Generated by Django 2.1.7 on 2019-09-16 06:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0020_remove_group_users_count'),
        ('projects', '0027_auto_20190807_0706'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
            ],
        ),
        migrations.CreateModel(
            name='WorkGroupMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('name', models.CharField(db_index=True, max_length=254, verbose_name='Name')),
                ('group_member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workgroup_assigned_to_user', to=settings.AUTH_USER_MODEL, verbose_name='Work Group Member')),
                ('work_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_group', to='projects.WorkGroup', verbose_name='WorkGroup')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='workgroup',
            name='group_members',
            field=models.ManyToManyField(blank=True, related_name='workgroup_assigned_to_users', through='projects.WorkGroupMember', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='workgroup',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='work_group_organization', to='authentication.Organization', verbose_name='WorkGroup Company'),
        ),
        migrations.AlterUniqueTogether(
            name='workgroup',
            unique_together={('name', 'organization')},
        ),
    ]
