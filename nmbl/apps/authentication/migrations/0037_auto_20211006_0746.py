# Generated by Django 2.2.17 on 2021-10-06 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0036_auto_20210910_1340'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permission',
            name='permission_category',
            field=models.CharField(choices=[('task', 'Task'), ('workflow', 'Workflow'), ('project', 'Project'), ('request', 'Request'), ('tasktemplate', 'Task template'), ('globalcustomfield', 'Global custom field')], max_length=20, verbose_name='Permission Category'),
        ),
    ]
