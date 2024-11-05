from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .abstract import WorkflowAbstract


class WorkflowFixture(WorkflowAbstract):
    project_template = models.ForeignKey(
        'ProjectTemplate',
        on_delete=models.CASCADE,
        related_name='workflow_fixtures',
        verbose_name=_('Project template'),
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

    class Meta:
        verbose_name = _('Workflow Fixture')
        verbose_name_plural = _('Workflow Fixtures')

    def clean(self):
        if self.due_date and self.start_date and self.due_date < self.start_date:
            raise ValidationError({'due_date': _('Due date must be greater than start date')})
