from authentication.models import BaseNameModel
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import PRIORITY_CHOICES


class ServiceDesk(BaseNameModel):
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='company_service_desk',
        verbose_name=_('Company ServiceDesk'),
    )
    user_email = models.EmailField(
        max_length=254,
        verbose_name=_('User E-mail Address'),
    )
    user_phone_number = models.CharField(
        blank=True,
        null=True,
        max_length=15,
    )
    title = models.CharField(
        null=True,
        blank=True,
        max_length=226,
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
    access_token = models.CharField(
        null=True,
        blank=True,
        max_length=500,
    )
    expiration_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Access Token Expiration Date'),
    )
    is_expire = models.BooleanField(
        default=False,
        verbose_name=_('Is Access Token Expired'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Is Request Deleted'),
    )

    def __str__(self):
        return str(self.name)
