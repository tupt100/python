from django.db import models
from django.utils.translation import gettext_lazy as _

from .abstract import WorkflowAbstract


class Workflow(WorkflowAbstract):
    project = models.ForeignKey(
        'projects.Project',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(class)s_assigned_project',
        verbose_name=_('Assigned Project'),
    )
    ranks = models.ManyToManyField(
        'authentication.User',
        through='WorkflowRank',
        related_name='%(class)s_ranks',
    )
