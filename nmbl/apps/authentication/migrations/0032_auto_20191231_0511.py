# Generated by Django 2.1.7 on 2019-12-31 05:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0031_companyinformation_font_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='first_name',
            field=models.CharField(blank=True, max_length=254, null=True, verbose_name='First Name'),
        ),
        migrations.AddField(
            model_name='invitation',
            name='last_name',
            field=models.CharField(blank=True, max_length=254, null=True, verbose_name='Last Name'),
        ),
    ]
