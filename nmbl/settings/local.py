import os

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.getenv('DATABASE_NAME'),
        'USER': os.getenv('DATABASE_USERNAME'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST'),
        'PORT': os.getenv('DATABASE_PORT')
    }
}

SITE_URL = os.getenv("SITE_URL")
NOTIFICATION_BASE_URL = os.getenv("NOTIFICATION_BASE_URL")

#SITE_URL = "http://18.219.81.84"
#SITE_URL = "http://proxy.stage-codal.net"
#SITE_URL = 'https://devnew.proxylegalapp.com'
#NOTIFICATION_BASE_URL = 'https://devnew.proxylegalapp.com'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.getenv('REDIS_HOST'), int(os.getenv('REDIS_PORT', '6379')))],
        },
    },
}

DEBUG=False
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# S3 bucket credentials
DEFAULT_FILE_STORAGE = 'customers.custom_storage.S3Boto3StorageCustom'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_DEFAULT_ACL = "private"
AWS_QUERYSTRING_AUTH = True
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_KMS_ACCOUNT_ID = os.getenv('AWS_KMS_ACCOUNT_ID')
AWS_KMS_KEY_ADMIN_USER = os.getenv('AWS_KMS_KEY_ADMIN_USER')
AWS_CALLING_FORMAT = '%s.s3-website-%s.amazonaws.com' % (AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME)
MEDIA_URL = 'http://%s.s3.amazonaws.com/images/' % AWS_STORAGE_BUCKET_NAME
#AWS_S3_OBJECT_PARAMETERS = {
#    'CacheControl': 'max-age=86400',
#    'ServerSideEncryption': 'aws:kms',
#    'SSEKMSKeyId': '13e64cec-8357-4677-824a-3dd63f5dfdd8'
#}

BROKER_URL = 'redis://%s:%s/%s' % (os.getenv('REDIS_HOST'), os.getenv('REDIS_PORT'), os.getenv('REDIS_CELERY_DATABASE_ID'))
BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 3600}  # 1 hour.
CELERY_RESULT_BACKEND = BROKER_URL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CORS_ORIGIN_ALLOW_ALL = True
ALLOWED_HOSTS = ['*']

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'base.api.drferrorhandler.exception_handler',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # 'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        # 'rest_framework.permissions.AllowAny',
        # 'rest_framework.permissions.DjangoModelPermissions',
    ),
    'DATETIME_FORMAT': "%Y-%m-%dT%H:%M:%SZ",
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 30,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_MODEL_SERIALIZER_CLASS': [
        'rest_framework.serializers.ModelSerializer',
    ],
    # 'DEFAULT_PARSER_CLASSES': [
    #     'rest_framework.parsers.FormParser',
    #     'rest_framework.parsers.MultiPartParser',
    #     'rest_framework.parsers.JSONParser',
    # ]
}

TENANT_AWS_DICT = {
    'devnew': {
        'AWS_STORAGE_BUCKET_NAME': 'proxydev',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '13e64cec-8357-4677-824a-3dd63f5dfdd8'
        }
    },
    'stagenew': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-stage',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '1d575169-d218-45fa-bb4e-656f36836ddf'
        }
    },
    'dev': {
        'AWS_STORAGE_BUCKET_NAME': 'proxydev',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '13e64cec-8357-4677-824a-3dd63f5dfdd8'
        }
    },
    'stage': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-stage',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '1d575169-d218-45fa-bb4e-656f36836ddf'
        }
    },
    'acumed': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-acumed',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': 'd14a778a-41a4-46be-8f40-0b3031e02fd8'
        }
    },
    'cps': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-cps',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '8eaed0e0-413e-4a35-afdf-d89fd266a10e'
        }
    },
    'inap': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-inap',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '0a8d1701-cebf-4d04-82e2-c79df2d37434'
        }
    },
    'mr': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-mr',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '9ee2bafa-a11c-425a-a6b7-d70b5d13003e'
        }
    },
    'vensure': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-vensure',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': 'c5d9a121-9037-48df-962d-2477b3cadb0a'
        }
    },
    'waymo': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-waymo',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '2b95cb5b-d97d-4f7b-86ae-af9bbf151466'
        }
    },
    'zebra': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-zebra',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': 'c822a83f-7b27-4ca3-8a1e-a4f8a2f3c322'
        }
    },
    'bigassfans': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-bigassfans',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': 'e142cb11-dd4f-4b83-8818-94d08e1327ef'
        }
    },
    'nmbl': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-nmbl',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '99ca8e26-3d4b-4325-ada3-fa419f02b4cd'
        }
    },
    'lisnr': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-lisnr',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '449a35ea-3ad0-4c3f-82b6-3b14e323f05e'
        }
    },
    'salary': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-salary',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '9f23862f-c07d-4fb2-9472-75e44ed3cbdb'
        }
    },
    'klg': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-klg',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '1dc0ec51-e328-4b5d-8af6-bf49858f0702'
        }
    },
    'incounsel': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-incounsel',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': 'd18beaa9-0abf-468d-b04a-7a66e42d856f'
        }
    },   
    'wne': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-wne',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '0408b8a1-5fc9-4df2-8554-f67394be3610'
        }
    },   
    'eggleston': {
        'AWS_STORAGE_BUCKET_NAME': 'proxy-eggleston',
        'AWS_S3_OBJECT_PARAMETERS': {
           'CacheControl': 'max-age=86400',
           'ServerSideEncryption': 'aws:kms',
           'SSEKMSKeyId': '8bb36b9e-29a1-4bf9-a515-9426c641268f'
        }
    }
}
POSTMARK_TOKEN = os.getenv('POSTMARK_TOKEN')
IMPROVMX_USERNAME = os.getenv('IMPROVMX_USERNAME')
IMPROVMX_AUTH = os.getenv('IMPROVMX_AUTH')
CELERY_KEY = os.getenv('CELERY_KEY')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DRF_RECAPTCHA_SECRET_KEY = os.getenv('DRF_RECAPTCHA_SECRET_KEY')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
    },
}