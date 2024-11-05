from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'nmbl',
        'USER': 'nmbl',
        'PASSWORD': 'password',
        'HOST': 'postgres',
        'PORT': '5432',
    }
}
ORIGINAL_BACKEND = 'django.contrib.gis.db.backends.postgis'
DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

DEFAULT_FROM = 'no-reply@proxylegalapp.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_HOST_USER = 'apikey'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# EMAIL_BACKEND = 'postmarker.django.EmailBackend'
# POSTMARK = {
#     'TOKEN': '<YOUR POSTMARK SERVER TOKEN>',
#     'TEST_MODE': False,
#     'VERBOSITY': 0,
# }

# file uploading limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 304857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 304857600
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000


SITE_URL = "https://{}.proxylegalapp.com"
NOTIFICATION_BASE_URL = "https://{}.proxylegalapp.com"

CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
# BROKER_URL = 'amqp://guest:**@127.0.0.1:5672'
# CELERY_RESULT_BACKEND = 'amqp://guest:**@127.0.0.1:5672'
BROKER_TRANSPORT = 'redis'
BROKER_URL = 'redis://redisapp:6379/10'
BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 3600}  # 1 hour.
CELERY_RESULT_BACKEND = 'redis://redisapp:6379/10'


CELERY_TIMEZONE = 'UTC'

CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'json'

# CELERY_IMPORTS = (

from datetime import timedelta

# CELERY_BEAT_SCHEDULE = {
#     'task-number-one': {
#         'task': 'projects.tasks.project_due_date_check',
#         'schedule': timedelta(seconds=86400),
#         'args': ()
#     },
# }

TENANT_AWS_DICT = {}
TENANT_LIMIT_SET_CALLS = True

import traceback
try:
    from .local import *
except Exception as e:
    print('Failed to load local settings: ' + str(e))
    print(traceback.format_exc())
