# Generated by Django 2.1.7 on 2019-11-26 11:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_companyinformation_message'),
    ]

    operations = [
        migrations.RenameField(
            model_name='companyinformation',
            old_name='content',
            new_name='background_color',
        ),
    ]
