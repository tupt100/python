from authentication.models import BaseModel
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceDeskExternalCCUser(BaseModel):
    email = models.EmailField(
        max_length=254,
        verbose_name=_('E-mail Address'),
    )
    message = models.ForeignKey(
        'ServiceDeskRequestMessage',
        null=True,
        on_delete=models.SET_NULL,
        related_name='user_message',
        verbose_name=_('Message'),
    )
    external_request = models.ForeignKey(
        'ServiceDeskExternalRequest',
        null=True,
        on_delete=models.SET_NULL,
        related_name='associate_external_request',
        verbose_name=_('Service Desk External Request'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='user_created_by',
        verbose_name=_('Created By'),
    )
