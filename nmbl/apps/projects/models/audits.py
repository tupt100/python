from authentication.models import BaseModel
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.translation import gettext_lazy as _

MODEL_CHOICES = (
    ("project", "Project"),
    ("workflow", "Workflow"),
    ("task", "Task"),
    ("attachment", "Attachment"),
    ("servicedesk", "ServiceDesk"),
    ("servicedeskrequest", "ServiceDeskRequest"),
)


class AuditHistory(BaseModel):
    model_reference = models.CharField(
        choices=MODEL_CHOICES,
        null=True,
        blank=True,
        max_length=225,
    )
    model_id = models.IntegerField(
        null=True,
        blank=True,
    )
    by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='modified_by',
        blank=True,
        verbose_name=_('By User'),
    )
    change_message = JSONField(
        null=True,
        blank=True,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='modified_to',
        verbose_name=_('To User'),
    )
    model_name = models.CharField(
        null=True,
        blank=True,
        max_length=225,
    )
    last_importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
    old_due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Old Due Date'),
    )
    new_due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('new Due Date'),
    )
    by_servicedesk_user = models.ForeignKey(
        'ServiceDeskUserInformation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='modified_by_servicedesk_user',
        verbose_name=_('Change By ServiceDeskUser'),
    )
