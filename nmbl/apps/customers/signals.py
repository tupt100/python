import boto3
from authentication.models import User
from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django_tenants.utils import schema_context

from .models import Domain, Client, Postmark, Feature, FeatureName
from .tasks import aws_resource_create, \
    create_default_data, create_postmark_server


def post_client_save(sender, instance, created, **kwargs):
    if created:
        items = []
        for f in FeatureName.values:
            items += [
                Feature(key=f, client=instance)
            ]
        per_items = Feature.objects.bulk_create(items)

    print('# post_client_save #')


def post_domain_save(sender, instance, created, **kwargs):
    Site.objects.get_or_create(
        domain=instance.domain, name=instance.domain)
    with schema_context(instance.tenant.schema_name):
        if 'localhost' not in instance.domain and '127.0.0.1' not in \
                instance.domain and instance.tenant.schema_name != "public":
            aws_resource_create(instance.tenant.schema_name)
            create_default_data(instance.tenant.schema_name)
            create_postmark_server.s(instance.domain).apply_async(
                countdown=30,
                ignore_result=True,
                max_retries=0)
        u_data = {
            'email': instance.tenant.owner_email,
            'username': instance.tenant.owner_email
        }
        user_obj, created = User.objects.get_or_create(
            **u_data)
        user_obj.set_password(
            instance.tenant.owner_password)
        user_obj.is_superuser = True
        user_obj.is_staff = True
        user_obj.save()


def post_postmark_save(sender, instance, created, **kwargs):
    create_postmark_server.delay(instance.domain_name.domain)
    print('# postmark server create#')


post_save.connect(post_postmark_save, sender=Postmark)
post_save.connect(post_domain_save, sender=Domain)
post_save.connect(post_client_save, sender=Client)
