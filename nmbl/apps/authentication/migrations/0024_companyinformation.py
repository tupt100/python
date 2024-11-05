# Generated by Django 2.1.7 on 2019-10-15 08:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0023_auto_20191011_0543'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyInformation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('logo_url', models.CharField(blank=True, max_length=500, null=True)),
                ('content', models.CharField(blank=True, max_length=1000, null=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='company_information', to='authentication.Organization', verbose_name='Company Information')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
