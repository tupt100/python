from authentication.models import BaseModel
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceDeskRequestMessage(BaseModel):
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_message',
        verbose_name=_('Project Message'),
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_message',
        verbose_name=_('Workflow Message'),
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_message',
        verbose_name=_('Task Message'),
    )
    servicedesk_request = models.ForeignKey(
        'ServiceDeskRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='servicedesk_request_message',
        verbose_name=_('ServiceDeskRequest Message'),
    )
    message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Message'),
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='message_created_by',
        verbose_name=_('Created By'),
    )
    reply_by_servicedeskuser = models.ForeignKey(
        'ServiceDeskUserInformation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='servicedeskuser_message',
        verbose_name=_('ServiceDeskRequest Message'),
    )
    is_external_message = models.BooleanField(
        default=False,
        verbose_name=_('Is External Message'),
    )
    is_internal_message = models.BooleanField(
        default=False,
        verbose_name=_('Is Internal Message'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Is Message Deleted'),
    )
    is_first_message = models.BooleanField(
        default=False,
        verbose_name=_('Is First Message'),
    )
