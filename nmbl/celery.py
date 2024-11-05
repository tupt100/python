from __future__ import absolute_import, unicode_literals

import os

from celery.schedules import crontab
from django.conf import settings
# from celery import Celery
from tenant_schemas_celery.app import CeleryApp as Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nmbl.settings.development')

app = Celery('nmbl')

app.config_from_object('django.conf:settings')
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('nmbl.settings.development', namespace='CELERY')

app.conf.broker_url = settings.BROKER_URL
app.conf.broker_transport_options = settings.BROKER_TRANSPORT_OPTIONS
app.conf.result_backend = settings.CELERY_RESULT_BACKEND
# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

CELERY_BEAT_SCHEDULE = "djcelery.schedulers.DatabaseScheduler"
app.conf.beat_schedule = {
    'task-number-one': {
        'task': 'projects.tasks.project_due_date_check',
        'schedule': crontab(minute=15, hour=4),
    },
}

# @app.task(bind=True)
# def debug_task(self):
#     print('Request: {0!r}'.format(self.request))
