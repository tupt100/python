# Generated by Django 2.1.7 on 2019-07-25 05:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0021_auto_20190717_1100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tag',
            name='tag',
            field=models.CharField(blank=True, max_length=254, null=True, verbose_name='Tag'),
        ),
    ]
