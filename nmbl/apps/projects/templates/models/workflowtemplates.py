from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from authentication.models import Organization
from .basetemplates import BaseTemplateModel


class WorkflowTemplate(BaseTemplateModel):
    project = models.ForeignKey(
        'projects.Project',
        verbose_name=_('Assigned Project'),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_assigned_project',
    )
    assigned_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='%(app_label)s_%(class)s_assigned_to_users',
        verbose_name=_('Assigned To'),
    )

    class Meta:
        verbose_name = _('Workflow template')
        verbose_name_plural = _('Workflow templates')
