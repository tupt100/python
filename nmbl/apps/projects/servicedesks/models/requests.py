from authentication.models import BaseNameModel
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import PRIORITY_CHOICES


class ServiceDeskRequest(BaseNameModel):
    user_information = models.ForeignKey(
        'ServiceDeskUserInformation',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='service_desk_user',
        verbose_name=_('ServiceDesk User'),
    )
    subject = models.CharField(
        null=True,
        blank=True,
        max_length=226,
    )
    description = models.CharField(
        null=True,
        blank=True,
        max_length=10000,
    )
    requested_due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Requested Due Date'),
    )
    assigned_to = models.CharField(
        null=True,
        blank=True,
        max_length=256,
    )
    request_priority = models.IntegerField(
        default=2,
        null=True,
        blank=True,
        choices=PRIORITY_CHOICES,
        verbose_name=_('Request Priority'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Is Request Deleted'),
    )
    is_internal_request = models.BooleanField(
        default=False,
        verbose_name=_('Is Internal Request'),
    )

    def __str__(self):
        return str(self.user_information)
