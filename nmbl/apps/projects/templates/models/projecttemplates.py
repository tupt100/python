from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .basetemplates import BaseTemplateModel


class ProjectTemplate(BaseTemplateModel):
    assigned_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='%(app_label)s_%(class)s_assigned_to_users',
        verbose_name=_('Assigned To'),
    )

    class Meta:
        verbose_name = _('Project template')
        verbose_name_plural = _('Project templates')
