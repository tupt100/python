# Generated by Django 2.1.7 on 2019-03-26 07:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('projects', '0003_auto_20190326_0608'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='task_organization', to='authentication.Organization', verbose_name='Company'),
        ),
        migrations.AddField(
            model_name='workflow',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_organization', to='authentication.Organization', verbose_name='Company'),
        ),
    ]
