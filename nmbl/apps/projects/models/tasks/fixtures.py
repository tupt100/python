from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .abstract import TaskAbstract, TaskAbstractManager


class TaskFixtureManager(TaskAbstractManager):
    pass


class TaskFixture(TaskAbstract):
    workflow_template = models.ForeignKey(
        'WorkflowTemplate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_fixtures',
        verbose_name=_('Workflow template'),
    )
    workflow_fixture = models.ForeignKey(
        'WorkflowFixture',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_fixtures',
        verbose_name=_('Workflow fixture'),
    )
    due_date = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
    )
    start_date = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
    )

    objects = TaskFixtureManager()

    class Meta:
        verbose_name = _('Task Fixture')
        verbose_name_plural = _('Task Fixtures')

    def clean(self):
        super(TaskFixture, self).clean()
        if self.workflow_template_id and self.workflow_fixture_id:
            raise ValidationError(_('You can not set both workflow template and workflow fixture'))

        if not self.workflow_template_id and not self.workflow_fixture_id:
            raise ValidationError(_('You must set either workflow template or workflow fixture'))

        if self.due_date and self.start_date and self.due_date < self.start_date:
            raise ValidationError({'due_date': _('Due date must be greater than start date')})
