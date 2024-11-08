# Generated by Django 2.1.7 on 2019-12-19 04:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0044_privilage_change_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='TagChangeLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('category_type', models.CharField(blank=True, choices=[('project', 'Project'), ('workflow', 'Workflow'), ('task', 'Task')], max_length=225, null=True)),
                ('tag', models.CharField(blank=True, max_length=225, null=True)),
                ('new', models.IntegerField(blank=True, default=0, null=True)),
                ('completed', models.IntegerField(blank=True, default=0, null=True)),
                ('changed_at', models.DateField(blank=True, db_index=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
