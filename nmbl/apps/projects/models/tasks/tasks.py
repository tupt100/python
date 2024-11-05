from django.db import models
from django.utils.translation import gettext_lazy as _

from .abstract import TaskAbstract, TaskAbstractManager


class TaskManager(TaskAbstractManager):
    pass


class Task(TaskAbstract):
    """
    Task model
    """

    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(class)s_workflow',
        verbose_name=_('Task Workflow'),
    )
    ranks = models.ManyToManyField(
        'authentication.User',
        through='TaskRank',
        related_name='%(class)s_ranks',
    )

    objects = TaskManager()

    class Meta:
        verbose_name = _('Task')
        verbose_name_plural = _('Tasks')
