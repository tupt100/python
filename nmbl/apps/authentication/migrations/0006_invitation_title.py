# Generated by Django 2.1.7 on 2019-04-03 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0005_auto_20190402_1431'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='title',
            field=models.CharField(blank=True, max_length=254, null=True, verbose_name='Title'),
        ),
    ]
