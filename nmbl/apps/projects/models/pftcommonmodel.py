from authentication.models import BaseNameModel
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import PR_WF_STATUS_CHOICES


class PFTCommonModel(BaseNameModel):
    """
    Common model for Project Workflow and task
    """

    class Meta:
        abstract = True

    status = models.IntegerField(
        choices=PR_WF_STATUS_CHOICES,
        default=1,
        verbose_name=_('Status'),
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
    )
    old_due_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_last_modified_by',
        verbose_name=_('Modified By'),
    )
    is_email_notified = models.BooleanField(
        default=False,
        verbose_name=_('Is Email Modified'),
    )
    is_assignee_changed = models.BooleanField(
        default=False,
        verbose_name=_('Is Assignee Changed'),
    )
    start_date = models.DateTimeField(
        db_index=True,
        null=True,
        blank=True,
        verbose_name=_('Due Date'),
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name=_('Is Private'),
    )
    # how much part of task/project/workflow is completed
    completed_percentage = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
