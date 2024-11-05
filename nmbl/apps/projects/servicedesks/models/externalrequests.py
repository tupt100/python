from authentication.models import BaseModel
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceDeskExternalRequest(BaseModel):
    service_desk_request = models.ForeignKey(
        'ServiceDeskRequest',
        null=True,
        blank=True,
        related_name='service_desk_external_request',
        on_delete=models.SET_NULL,
        verbose_name=_('ServiceDesk External Request'),
    )
    servicedeskuser = models.ForeignKey(
        'ServiceDeskUserInformation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='request_to_servicedeskrequest',
        verbose_name=_('ServiceDesk Task User'),
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_servicedeskrequest',
        verbose_name=_('ServiceDesk Task'),
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_servicedeskrequest',
        verbose_name=_('ServiceDesk Workflow'),
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_servicedeskrequest',
        verbose_name=_('ServiceDesk Project'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='task_request_created_by',
        verbose_name=_('Created By'),
    )
    replies = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
