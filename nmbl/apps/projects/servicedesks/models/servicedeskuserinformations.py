from authentication.models import BaseModel
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceDeskUserInformation(BaseModel):
    user_name = models.CharField(
        null=True,
        blank=True,
        max_length=500,
    )
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='company_service_desk_user',
        verbose_name=_('Company ServiceDesk User Information'),
    )
    user_email = models.EmailField(
        max_length=254,
        verbose_name=_('E-mail Address'),
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

    def __str__(self):
        return str(self.user_email)
