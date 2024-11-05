# Generated by Django 2.1.7 on 2019-11-21 13:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0041_auto_20191119_0935'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='servicedeskuser_attachment', to='projects.ServiceDeskUserInformation'),
        ),
        migrations.AddField(
            model_name='audithistory',
            name='by_servicedesk_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_by_servicedesk_user', to='projects.ServiceDeskUserInformation', verbose_name='Change By ServiceDeskUser'),
        ),
    ]
