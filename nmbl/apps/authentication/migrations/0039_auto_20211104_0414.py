# Generated by Django 2.2.17 on 2021-11-04 04:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0038_auto_20211029_0551'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permission',
            name='permission_category',
            field=models.CharField(choices=[('task', 'Task'), ('workflow', 'Workflow'), ('project', 'Project'), ('request', 'Request'), ('tasktemplate', 'Task template'), ('globalcustomfield', 'Global custom field'), ('workflowtemplate', 'Workflow template'), ('projecttemplate', 'Project template')], max_length=20, verbose_name='Permission Category'),
        ),
    ]
