# Generated by Django 2.1.7 on 2019-12-19 12:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0047_groupworkloadlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupworkloadlog',
            name='group_name',
            field=models.CharField(blank=True, max_length=225, null=True),
        ),
    ]
