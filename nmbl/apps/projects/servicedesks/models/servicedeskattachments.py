from authentication.models import BaseModel
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceDeskAttachment(BaseModel):
    document = models.FileField(
        upload_to='ServiceDeskDocuments/',
    )
    document_name = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )
    uploaded_by = models.EmailField(
        max_length=254,
        verbose_name=_('Uploader E-mail Address'),
    )
    service_desk = models.ForeignKey(
        'ServiceDesk',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='service_desk_attachment',
        verbose_name=_('Service Desk Attachment'),
    )
    can_remove = models.BooleanField(
        default=True,
        verbose_name=_('Attachment Remove'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Attachment Deleted'),
    )
    service_desk_request = models.ForeignKey(
        'ServiceDeskRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='service_desk_request_attachment',
        verbose_name=_('Service Desk Attachment'),
    )
