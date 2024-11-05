## Clone the project
Clone the project from Github:

    git clone https://github.com/codal/proxy-mvp.git


## Install Python
    
    sudo apt-get update && sudo apt-get install python3.7 virtualenv


# OS Dependencies

    sudo apt-get update &&  sudo apt-get install python3-dev python3.7-dev python3.6-dev build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev


## Install PostgreSQL

    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
    
    sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -sc)-pgdg main" > /etc/apt/sources.list.d/PostgreSQL.list'
    
    sudo apt-get update
    
    sudo apt-get install postgresql-10


## Database    
Create empty database for the application (e.g. nmbl ):

    sudo -u postgresql psql

    CREATE DATABASE nmbl_dev;


## Settings

Edit Django settings file according to the requirements

## Migrate Database

    ./manage.py makemigrations
    
    ./manage.py migrate

## Load base data

Load fixtures:

    ./manage.py loaddata nmbl/fixtures/authentication_group.json
    ./manage.py loaddata nmbl/fixtures/authentication_permission.json
    ./manage.py loaddata nmbl/fixtures/authentication_default_permission.json
    ./manage.py loaddata nmbl/fixtures/notifications_notificationtype.json
    ./manage.py loaddata nmbl/fixtures/notifications_default_notification_settings.json 

## Install Apache Web Server

    sudo apt-get update && sudo apt-get install apache2 

Enable modules:

    sudo a2enmod rewrite

If We need ssl:

    sudo a2enmod ssl

## Install WSGI Dependencies

    sudo apt-get update && sudo apt-get install libapache2-mod-wsgi-py3

    
> **Note:** More information [here](https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/modwsgi/) and [here](https://www.digitalocean.com/community/tutorials/how-to-serve-django-applications-with-apache-and-mod_wsgi-on-debian-8)


# Deploy with Docker

## Install Docker

    - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    - sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    - sudo apt-get update
    - sudo apt-get install -y docker-ce
    - sudo service docker start
    - sudo service docker status

##  Run docker command without sudo
    - sudo groupadd docker
    - sudo usermod -aG docker $USER
    - Restart the system.

## Install Docker Compose
    - sudo curl -L "https://github.com/docker/compose/releases/download/1.23.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    - sudo chmod +x /usr/local/bin/docker-compose

## Run the Docker Compose to start the system
    - docker-compose up -d --force-recreate --build
    - docker-compose exec nmblapp bash -c "cd /opt/services/app/src && python manage.py migrate"
    - docker-compose exec nmblapp bash -c "cd /opt/services/app/src && python manage.py loaddata */fixtures/*.json"
    - docker-compose exec nmblapp bash -c "cd /opt/services/app/src && python manage.py collectstatic --no-input"
    -docker-compose logs -f nmblceleryapp

## Multi-tenant Configuration 
​
#### public schema migrations
    python manage.py migrate_schemas
    python manage.py migrate_schemas --shared
​
#### create your public tenant (Mandatory)
    from customers.models import Client, Domain
    tenant = Client(schema_name='public',
                    name='Codal Inc.',
                    paid_until='2020-05-05',
                    on_trial=False,
                    owner_email='admin@codaldemo.com',
                    owner_password='Codal@401')
    tenant.save()

##### Add one or more domains for the tenant
    domain = Domain()
    domain.domain = 'localhost' # don't add your port or www here! on a local server you'll want to use localhost here
    domain.tenant = tenant
    domain.is_primary = True
    domain.save()
##### create site(Not needed as moved to Domain() signal)
    from django.contrib.sites.models import Site
    new_site = Site.objects.create(domain='localhost', name='localhost')
​
#### create your first real tenant
    from customers.models import Client, Domain
    tenant = Client(schema_name='dev',
                    name='Tenant',
                    paid_until='2020-12-05',
                    on_trial=True,
                    owner_email='dev@codaldemo.com',
                    owner_password='Codal@123')
    tenant.save() # migrate_schemas automatically called, your tenant is ready to be used!

##### Add one or more domains for the tenant
    domain = Domain()
    domain.domain = 'dev.localhost' # don't add your port or www here!
    domain.tenant = tenant
    domain.is_primary = True
    domain.save()

##### create site(Not needed as moved to Domain() signal)
    from django.contrib.sites.models import Site
    Site.objects.create(domain='dev.localhost', name='dev.localhost')

##### create site /etc/hosts entry  (for localhost only)
    127.0.0.1   tenant.localhost
​
#### create superuser for public schema
    python manage.py createsuperuser
    - admin@codaldemo.com / Codal@401

 #### To create superuser for any tenant
    python manage.py create_tenant_superuser --username=tenant@codaldemo.com --schema=tenant

#### To view tenant admin
    go to tenant.localhost:8000/admin
