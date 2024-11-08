# Generated by Django 2.1.7 on 2019-04-02 07:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_auto_20190327_0559'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('modified_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified At')),
                ('has_permission', models.BooleanField(default=False, verbose_name='Has Permission')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='default_permission_group', to='authentication.Group', verbose_name='Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='default_permission_permission', to='authentication.Permission', verbose_name='Group Permission')),
            ],
        ),
        migrations.AddField(
            model_name='group',
            name='default_permissions',
            field=models.ManyToManyField(related_name='default_permissions', through='authentication.DefaultPermission', to='authentication.Permission'),
        ),
        migrations.AlterUniqueTogether(
            name='defaultpermission',
            unique_together={('group', 'permission')},
        ),
    ]
