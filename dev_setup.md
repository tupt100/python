### Start docker-compose stack
```bash
$ docker-compose up -d
```

### Check that everything is running okay
```bash
$ docker-compose ps
```

### Check the logs
```bash
$ docker-compose logs
```

### Start a shell
```bash
$ docker-compose exec nmblapp bash
```

### Setup automatically

```bash
python manage.py devsetup
```

If you ran above command, You can ignore the below sections. Credentials is [here](#access-the-web-app).


### Run the following commands in the shell
```bash
./manage.py migrate
./manage.py loaddata nmbl/fixtures/authentication_group.json
./manage.py loaddata nmbl/fixtures/authentication_permission.json
./manage.py loaddata nmbl/fixtures/authentication_default_permission.json
./manage.py loaddata nmbl/fixtures/notifications_notificationtype.json
./manage.py loaddata nmbl/fixtures/notifications_default_notification_settings.json 
```

### Start a python shell
```bash
./manage.py shell
```

### Edit the variables in this python snippet if required and execute it in the python shell
```python
# Change these as you see fit
admin_email='admin@localhost'
admin_password='Password123!'
tenant_email='admin@dev.localhost'
tenant_password='Password123!'
admin_tenant_name='Admin Tenant'
tenant_name='Tenant'
tenant_subdomain='dev'

from customers.models import Client, Domain
admin_tenant = Client(schema_name='public',
                name=admin_tenant_name,
                paid_until='2022-12-31',
                on_trial=False,
                owner_email=admin_email,
                owner_password=admin_password)
admin_tenant.save()

admin_domain = Domain()
admin_domain.domain = 'localhost' # don't add your port or www here
admin_domain.tenant = admin_tenant
admin_domain.is_primary = True
admin_domain.save()

tenant = Client(schema_name=tenant_subdomain,
                name=tenant_name,
                paid_until='2022-12-31',
                on_trial=True,
                owner_email=tenant_email,
                owner_password=tenant_password)
tenant.save()

domain = Domain()
domain.domain = '{}.localhost'.format(tenant_subdomain)
domain.tenant = tenant
domain.is_primary = True
domain.save()
exit()
```

### Run the following commands in the shell for `dev`

```bash
python manage.py tenant_command loaddata --schema=dev nmbl/fixtures/authentication_group.json
python manage.py tenant_command loaddata --schema=dev nmbl/fixtures/authentication_permission.json
python manage.py tenant_command loaddata --schema=dev nmbl/fixtures/authentication_default_permission.json
python manage.py tenant_command loaddata --schema=dev nmbl/fixtures/notifications_notificationtype.json
python manage.py tenant_command loaddata --schema=dev nmbl/fixtures/notifications_default_notification_settings.json
python manage.py shell
```

```python
from django_tenants.utils import schema_context
from authentication.models import Organization, Group, User
schema_name = 'dev'
org_name = 'Dev Org'
email = f'user@{schema_name}.localhost'
raw_password='Password123!'

with schema_context(schema_name):
    org = Organization.objects.create(name=org_name)
    try:
        # catch raise sending email error
        org.owner_email=email
        org.save()
    except:
        pass
    group = Group.objects.get(name__icontains='admin')
    user = User.objects.create(email=email, group_id=group.pk, company_id=org.pk)
    user.set_password(raw_password=raw_password)
    user.save()

exit()      
```

### Add an entry for your tenant to your `/etc/hosts` file (not in docker)
```
127.0.0.1 dev.localhost
```

### Access the web app
You should be able to access the admin tenant control panel at:
  * [http://localhost:8000/admin](http://localhost:8000/admin)
  * Credentials is:
  
```
username=admin@localhost
password=Password123!
```
        
You can also access the tenant control panel at:
  * [http://dev.localhost:8000/admin](http://dev.localhost:8000/admin)
  * Credentials are:
  
```
username=admin@dev.localhost
password=Password123!

username=user@dev.localhost
password=Password123!
```

### Dump and update fixtures

```shell
python manage.py tenant_command dumpdata authentication.permission --indent=4 --schema=dev --format=json > nmbl/fixtures/authentication_permission.json
python manage.py tenant_command dumpdata authentication.defaultpermission --indent=4 --schema=dev --format=json > nmbl/fixtures/authentication_default_permission.json

```
