from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import (
    IMPORTANCE_CHOICES,
    CustomFieldValueMixin,
    PFTCommonModel,
    default_task_importance,
)


class WorkflowAbstract(PFTCommonModel, CustomFieldValueMixin):
    # Assign to a Group
    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Workflow Priority'),
    )
    attachments = GenericRelation(
        'Attachment',
        object_id_field='object_id',
        content_type_field='content_type',
        related_query_name='%(app_label)s_%(class)s_content_object',
    )
    workflow_tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='%(class)s_tags',
        verbose_name=_('Workflow Tag'),
    )
    task_importance = JSONField(
        default=default_task_importance,
    )
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(class)s_organization',
        verbose_name=_('Company'),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_owner',
        verbose_name=_('Owner'),
    )
    assigned_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='%(class)s_assigned_to_users',
        verbose_name=_('Assigned To'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_created_by',
        verbose_name=_('Created By'),
    )

    # Attorney Client privilege - Workflow
    attorney_client_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Workflow Privilege Attorney Client"),
    )
    # Work Product privilege - Workflow
    work_product_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Workflow Privilege Work Product"),
    )
    # Confidential privilege - Workflow
    confidential_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Workflow Privilege Confidential"),
    )
    assigned_to_group = models.ManyToManyField(
        'WorkGroup',
        related_name='%(class)s_assigned_to_workgroup',
        blank=True,
        verbose_name=_('WorkGroup Workflow'),
    )

    template = models.ForeignKey(
        'projects.WorkflowTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Workflow template'),
    )

    def __str__(self):
        return str(self.name)

    def clean(self):
        self.custom_fields_value = self.prepare_custom_fields_value(self.template, self.custom_fields_value)
        self.clean_custom_fields_value(self.template, self.custom_fields_value)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
