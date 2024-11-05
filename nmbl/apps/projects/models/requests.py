from authentication.models import BaseNameModel
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import IMPORTANCE_CHOICES


class Request(BaseNameModel):
    request_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='request_by_user',
        verbose_name=_('Assigned To'),
    )
    due_date = models.DateTimeField(
        null=True,
        verbose_name=_('Due Date'),
    )
    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Request Priority'),
    )
    attachments = GenericRelation(
        'Attachment',
        object_id_field='object_id',
        content_type_field='content_type',
        related_query_name='%(app_label)s_%(class)s_content_object',
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='request_created_by',
        verbose_name=_('Created By'),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='request_assigned_by_user',
        blank=True,
        verbose_name=_('Assigned By'),
    )

    def __str__(self):
        return str(self.name)
