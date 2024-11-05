from django_tenants.utils import schema_context
from projects.models import AWSCredential
from storages.backends.s3boto3 import S3Boto3Storage


class S3Boto3StorageCustom(S3Boto3Storage):

    def _save(self, name, content):
        from django.db import connection
        with schema_context(connection.schema_name):
            aws_obj = AWSCredential.objects.first()
            if aws_obj and aws_obj.bucket_name and aws_obj.kms_key:
                self.object_parameters = {'CacheControl': 'max-age=86400',
                                          'ServerSideEncryption': 'aws:kms',
                                          'SSEKMSKeyId': aws_obj.kms_key}
                self.bucket_name = aws_obj.bucket_name
            return super(S3Boto3StorageCustom, self)._save(name, content)

    @property
    def bucket(self):
        """
        Get the current bucket.
        """
        from django.db import connection
        with schema_context(connection.schema_name):
            aws_obj = AWSCredential.objects.first()
            if aws_obj and aws_obj.bucket_name and aws_obj.kms_key:
                self.object_parameters = {'CacheControl': 'max-age=86400',
                                          'ServerSideEncryption': 'aws:kms',
                                          'SSEKMSKeyId': aws_obj.kms_key}
                self.bucket_name = aws_obj.bucket_name
        self._bucket = self._get_or_create_bucket(self.bucket_name)
        return self._bucket
