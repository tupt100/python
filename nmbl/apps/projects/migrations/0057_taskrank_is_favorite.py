# Generated by Django 2.1.7 on 2020-03-06 05:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0056_auto_20200130_1105'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskrank',
            name='is_favorite',
            field=models.BooleanField(default=False),
        ),
    ]
