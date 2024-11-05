from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
from django.db import connection, models
from django.utils.translation import ugettext_lazy as _
from projects.models import (
    IMPORTANCE_CHOICES,
    CustomFieldValueMixin,
    PFTCommonModel,
    default_task_importance,
)


class Project(PFTCommonModel, CustomFieldValueMixin):
    """ """

    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Project Priority'),
    )
    attachments = GenericRelation(
        'Attachment',
        object_id_field='object_id',
        content_type_field='content_type',
        related_query_name='%(app_label)s_%(class)s_content_object',
    )
    project_tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='project_tags',
        verbose_name=_('Project Tag'),
    )
    task_importance = JSONField(
        default=default_task_importance,
    )
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='project_organization',
        verbose_name=_('Company'),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=False,
        on_delete=models.CASCADE,
        related_name='project_owner',
        verbose_name=_('Owner'),
    )
    assigned_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='project_assigned_to_users',
        verbose_name=_('Assigned To'),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='project_assigned_by_user',
        verbose_name=_('Assigned By'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='project_created_by',
        verbose_name=_('Created By'),
    )
    ranks = models.ManyToManyField(
        'authentication.User',
        through='ProjectRank',
        related_name='project_ranks',
    )
    # Attorney Client privilege - Project
    attorney_client_privilege = models.BooleanField(
        default=False,
        verbose_name=_('Project Privilege Attorney Client'),
    )
    # Work Product privilege - Project
    work_product_privilege = models.BooleanField(
        default=False,
        verbose_name=_('Project Privilege Work Product'),
    )
    # Confidential privilege - Project
    confidential_privilege = models.BooleanField(
        default=False,
        verbose_name=_('Project Privilege Confidential'),
    )
    assigned_to_group = models.ManyToManyField(
        'WorkGroup',
        verbose_name=_('WorkGroup Project'),
        related_name='project_assigned_to_workgroup',
        blank=True,
    )

    template = models.ForeignKey(
        'projects.ProjectTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Project template'),
    )

    def __str__(self):
        return str(self.name)

    def clean(self):
        self.custom_fields_value = self.prepare_custom_fields_value(self.template, self.custom_fields_value)
        self.clean_custom_fields_value(self.template, self.custom_fields_value)

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Project, self).save(*args, **kwargs)


class ProjectRank(models.Model):
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
    )
    rank = models.PositiveIntegerField(
        default=1,
    )
    is_active = models.BooleanField(
        default=True,
    )

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))
