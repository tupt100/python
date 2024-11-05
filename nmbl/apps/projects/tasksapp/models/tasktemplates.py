from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import IMPORTANCE_CHOICES

from nmbl.apps.base.db import BaseModel, BaseModelManager, BaseModelQuerySet


class TaskTemplateQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(TaskTemplateQueryset, self).__init__(*args, **kwargs)

    def active(self):
        return super(TaskTemplateQueryset, self).active().filter(is_delete=False)


class TaskTemplateManager(BaseModelManager):
    def get_queryset(self):
        return TaskTemplateQueryset(self.model, using=self._db)


class TaskTemplate(BaseModel):
    title = models.CharField(max_length=40, null=False, blank=False, verbose_name=_('Title'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        on_delete=models.PROTECT,
        verbose_name=_('Created By'),
    )
    task_name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('Task name'))
    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Task Priority'),
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tasktemplate_workflow',
        verbose_name=_('Task Workflow'),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tasktemplate_assigned_to_user',
        verbose_name=_('Assigned To'),
    )
    assigned_to_group = models.ManyToManyField(
        'WorkGroup',
        blank=True,
        related_name='tasktemplate_assigned_to_workgroup',
        verbose_name=_('WorkGroup Task'),
    )
    due_date = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
    )
    start_date = models.PositiveIntegerField(
        db_index=True,
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
    )
    description = models.TextField(
        verbose_name=_('Description'),
        blank=True,
        null=True,
    )
    is_private = models.BooleanField(
        verbose_name=_('Is Private'),
        default=False,
    )
    # Attorney Client privilege - Task
    attorney_client_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Attorney Client",
    )
    # Work Product privilege - Task
    work_product_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Work Product",
    )
    # Confidential privilege - Task
    confidential_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Confidential",
    )
    is_delete = models.BooleanField(verbose_name=_('Task Template Delete'), default=False)

    objects = TaskTemplateManager()

    class Meta:
        verbose_name = _('Task template')
        verbose_name_plural = _('Task templates')

    def __str__(self):
        return '{}'.format(self.title)

    def clean(self):
        super(TaskTemplate, self).clean()
        if self.due_date and self.start_date and self.due_date < self.start_date:
            raise ValidationError({'due_date': _('Due date must be greater than start date')})
