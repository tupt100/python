# Generated by Django 2.1.7 on 2019-10-11 05:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0021_group_is_company_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='can_be_delete',
            field=models.BooleanField(default=False, verbose_name='Can Be Delete'),
        ),
    ]
