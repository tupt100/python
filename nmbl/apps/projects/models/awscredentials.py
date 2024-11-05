from authentication.models import BaseModel
from django.db import models


class AWSCredential(BaseModel):
    bucket_name = models.TextField(null=True, blank=True)
    kms_key = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.bucket_name)
