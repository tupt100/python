# Generated by Django 2.1.7 on 2019-11-22 10:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0042_auto_20191121_1358'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audithistory',
            name='model_reference',
            field=models.CharField(blank=True, choices=[('project', 'Project'), ('workflow', 'Workflow'), ('task', 'Task'), ('attachment', 'Attachment'), ('servicedesk', 'ServiceDesk'), ('servicedeskrequest', 'ServiceDeskRequest')], max_length=225, null=True),
        ),
    ]
