from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .management import create_feature_permission_for_client

class CustomerConfig(AppConfig):
    name = 'customers'

    def ready(self):
        import customers.signals
        post_migrate.connect(
            create_feature_permission_for_client,
            dispatch_uid="customers.management.create_feature_permission_for_client"
        )
