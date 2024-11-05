import boto3
import requests
from authentication.models import IntroSlide
from celery import shared_task
from django.conf import settings
from django.core.files import File
from django_tenants.utils import schema_context
from projects.models import AWSCredential


def create_default_data(schema_name):
    from django.core.management import call_command
    with schema_context(schema_name):
        call_command("loaddata", "nmbl/fixtures/authentication_intro_slides")
        call_command("loaddata", "nmbl/fixtures/authentication_group")
        call_command("loaddata", "nmbl/fixtures/authentication_permission")
        call_command("loaddata", "nmbl/fixtures/authentication_default_permission")
        call_command("loaddata", "nmbl/fixtures/notifications_notificationtype")


@shared_task
def upload_intro_slides(schema_name):
    with schema_context(schema_name):
        for instance in IntroSlide.objects.all():
            with open('nmbl/intro_slides/{}.png'.format(instance.id), 'rb') as f:
                instance.image.save('{}.png'.format(instance.title), File(f))


def create_aws_obj(schema_name, bucket_name, final_kms_key):
    with schema_context(schema_name):
        AWSCredential.objects.get_or_create(
            bucket_name=bucket_name,
            kms_key=final_kms_key)
        upload_intro_slides.s(schema_name).apply_async(countdown=120,
                                                       ignore_result=True,
                                                       max_retries=0)

def aws_kms_policy(account_id, key_admin_user):
    root_arn = "arn:aws:iam::{}:root".format(account_id)
    user_arn = "arn:aws:iam::{}:user/{}".format(account_id, key_admin_user)

    policy_template = """
            {
            "Id": "key-consolepolicy-3",
            "Version": "2012-10-17",
            "Statement": [{
                          "Sid": "Enable IAM User Permissions",
                          "Effect": "Allow",
                          "Principal": {"AWS": "%s"},
                          "Action": ["kms:*"],
                          "Resource": "*"
                          },
                          {
                          "Sid": "Allow access for Key Administrators",
                          "Effect": "Allow",
                          "Principal": {"AWS": "%s"},
                          "Action": [
                               "kms:Create*",
                               "kms:Describe*",
                               "kms:Enable*",
                               "kms:List*",
                               "kms:Put*",
                               "kms:Update*",
                               "kms:Revoke*",
                               "kms:Disable*",
                               "kms:Get*",
                               "kms:Delete*",
                               "kms:TagResource",
                               "kms:UntagResource",
                               "kms:ScheduleKeyDeletion",
                               "kms:CancelKeyDeletion"
                          ],
                          "Resource": "*"
                          },
                          {
                          "Sid": "Allow use of the key",
                          "Effect": "Allow",
                          "Principal": {"AWS": "%s"},
                          "Action": [
                              "kms:Encrypt",
                              "kms:Decrypt",
                              "kms:ReEncrypt*",
                              "kms:GenerateDataKey*",
                              "kms:DescribeKey"
                          ],
                          "Resource": "*"
                          },
                          {
                          "Sid": "Allow attachment of persistent resources",
                          "Effect": "Allow",
                          "Principal": {"AWS": "%s"},
                          "Action": [
                              "kms:CreateGrant",
                              "kms:ListGrants",
                              "kms:RevokeGrant"
                          ],
                          "Resource": "*",
                          "Condition": {
                              "Bool": {
                                  "kms:GrantIsForAWSResource": "true"
                              }
                          }
                      }
                  ]
    }"""
    return policy_template % (root_arn, user_arn, user_arn, user_arn)


def aws_resource_create(schema_name):
    s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                      aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                      region_name=settings.AWS_S3_REGION_NAME)
    kms = boto3.client('kms', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                       region_name=settings.AWS_S3_REGION_NAME)
    policy = aws_kms_policy(settings.AWS_KMS_ACCOUNT_ID, settings.AWS_KMS_KEY_ADMIN_USER)

    # create s3 bucket
    s3_bucket = {
        'ACL': settings.AWS_DEFAULT_ACL,
        'Bucket': 'proxy-{}'.format(schema_name),
        'CreateBucketConfiguration': {'LocationConstraint': settings.AWS_S3_REGION_NAME},
        'ObjectLockEnabledForBucket': False,
    }
    s3.create_bucket(**s3_bucket)
    # create kms key
    kms_key = {
        'Description': '{} tenant'.format(schema_name),
        'Origin': 'AWS_KMS',
        'Tags': [
            {
                'TagKey': 'name',
                'TagValue': '{}-nmbl-kms'.format(schema_name)
            },
        ]
    }
    kms_response = kms.create_key(**kms_key)
    final_kms_key = kms_response['KeyMetadata'].get('KeyId')
    kms.create_alias(
        AliasName='alias/{}-nmbl-kms'.format(schema_name),
        TargetKeyId=final_kms_key
    )
    kms.put_key_policy(
        KeyId=final_kms_key,
        Policy=policy,
        PolicyName='default')
    s3.put_bucket_cors(
        Bucket='proxy-{}'.format(schema_name),
        CORSConfiguration={
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['PUT', 'GET', 'POST'],
                    'AllowedOrigins': ['*']
                },
            ]
        },
    )
    s3.put_public_access_block(
        Bucket='proxy-{}'.format(schema_name),
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True
        }
    )
    s3.put_bucket_versioning(
        Bucket='proxy-{}'.format(schema_name),
        VersioningConfiguration={
            'Status': 'Enabled',
        }
    )
    s3.put_bucket_encryption(
        Bucket='proxy-{}'.format(schema_name),
        ServerSideEncryptionConfiguration={
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'aws:kms',
                        'KMSMasterKeyID': kms_response['KeyMetadata'].get('Arn')
                    }
                },
            ]
        }
    )
    create_aws_obj(schema_name, 'proxy-{}'.format(schema_name), final_kms_key)


@shared_task
def create_postmark_server(domain):
    try:
        # create postmark server for inbound emails
        json_data = {
            "Name": "{} - common inbound".format(domain.split('.')[0]),
            "Color": "red",
            "SmtpApiActivated": True,
            "RawEmailEnabled": False,
            "DeliveryHookUrl": "",
            "InboundHookUrl": "https://{}/projects/project_task_common_create_postmark/".format(domain),
            "BounceHookUrl": "",
            "IncludeBounceContentInHook": False,
            "OpenHookUrl": "",
            "PostFirstOpenOnly": False,
            "TrackOpens": False,
            "TrackLinks": "None",
            "ClickHookUrl": "",
            "InboundDomain": "{}".format(domain),
            "InboundSpamThreshold": 0,
            "EnableSmtpApiErrorHooks": False
        }
        postmark_response = requests.post(
            url='https://api.postmarkapp.com/servers',
            json=json_data,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "X-Postmark-Account-Token":
                         settings.POSTMARK_TOKEN
                     })
        if postmark_response.status_code == 200 and postmark_response.json():
            inbound_address = postmark_response.json().get('InboundAddress')
            print('inbound address:::::', inbound_address)
    except Exception as expn:
        print("No MX entry in DNS ", expn)
