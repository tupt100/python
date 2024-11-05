from authentication.models import Group, Organization, User
from customers.models import Client, Domain
from django.core import management
from django.core.management import get_commands, load_command_class
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = 'Load data and dev setup.'
    default_password = 'Password123!'
    master_domain = 'localhost'

    def _setup_super_admin(self):
        management.call_command('loaddata', "nmbl/fixtures/authentication_group.json")
        management.call_command('loaddata', "nmbl/fixtures/authentication_permission.json")
        management.call_command('loaddata', "nmbl/fixtures/authentication_default_permission.json")
        management.call_command('loaddata', "nmbl/fixtures/notifications_notificationtype.json")
        management.call_command('loaddata', "nmbl/fixtures/notifications_default_notification_settings.json")
        self.stdout.write(self.style.SUCCESS(f'Successfully load default fixtures.'))

        admin_email = f'admin@{self.master_domain}'
        admin_password = self.default_password
        admin_tenant_name = 'Admin Tenant'
        admin_tenant = Client(
            schema_name='public',
            name=admin_tenant_name,
            paid_until='2022-12-31',
            on_trial=False,
            owner_email=admin_email,
            owner_password=admin_password,
        )
        admin_tenant.save()

        admin_domain = Domain()
        admin_domain.domain = 'localhost'  # don't add your port or www here
        admin_domain.tenant = admin_tenant
        admin_domain.is_primary = True
        admin_domain.save()

    def _setup_tenant(self, schema_name):
        tenant_email = f'admin@{schema_name}.{self.master_domain}'
        tenant_password = self.default_password

        tenant_name = 'Tenant'
        tenant_subdomain = schema_name
        org_name = f'{schema_name} org'
        email = f'user@{schema_name}.{self.master_domain}'
        raw_password = self.default_password
        tenant = Client(
            schema_name=tenant_subdomain,
            name=tenant_name,
            paid_until='2022-12-31',
            on_trial=True,
            owner_email=tenant_email,
            owner_password=tenant_password,
        )
        tenant.save()

        domain = Domain()
        domain.domain = '{}.localhost'.format(tenant_subdomain)
        domain.tenant = tenant
        domain.is_primary = True
        domain.save()

        self.loaddata(schema_name, "nmbl/fixtures/authentication_group.json")
        self.loaddata(schema_name, "nmbl/fixtures/authentication_permission.json")
        self.loaddata(schema_name, "nmbl/fixtures/authentication_default_permission.json")
        self.loaddata(schema_name, "nmbl/fixtures/notifications_notificationtype.json")
        self.loaddata(schema_name, "nmbl/fixtures/notifications_default_notification_settings.json")

        self.stdout.write(self.style.SUCCESS(f'Successfully load fixtures for: {schema_name}.'))

        with schema_context(schema_name):
            org = Organization.objects.create(name=org_name)
            try:
                # catch raise sending email error
                org.owner_email = email
                org.save()
            except:
                pass
            group = Group.objects.get(name__icontains='admin')
            admin_user = User.objects.get(email=tenant_email)
            admin_user.group = group
            admin_user.first_name = 'Admin'
            admin_user.last_name = 'Tenant'
            admin_user.company = org
            admin_user.save()
            user = User.objects.create(
                email=email, first_name='First name', last_name='Last name', group_id=group.pk, company_id=org.pk
            )
            user.set_password(raw_password=raw_password)
            user.save()
        self.stdout.write(self.style.SUCCESS(f'Successfully setup organization: {schema_name}.'))

    def loaddata(self, schema_name, file):
        app_name = get_commands()["loaddata"]
        if isinstance(app_name, BaseCommand):
            # If the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, "loaddata")

        tenant = Client.objects.get(schema_name=schema_name)
        connection.set_tenant(tenant)
        self.stdout.write(self.style.SUCCESS(file))
        argv = ["loaddata", "--fixture", file]
        klass.run_from_argv(argv)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Load data and dev setup...'))
        self.stdout.write(self.style.SUCCESS('Start migration...'))

        management.call_command('migrate')
        self.stdout.write(self.style.SUCCESS('Finish migration.'))

        self._setup_super_admin()

        self.stdout.write(self.style.SUCCESS('Start migration for tenant...'))
        schema_name = "dev"

        self._setup_tenant(schema_name)

        self.stdout.write(self.style.SUCCESS('Successfully finish dev setup.'))
