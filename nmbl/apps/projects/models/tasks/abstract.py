from authentication.models import GroupAndPermission
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from projects.models import IMPORTANCE_CHOICES, PFTCommonModel


class TaskAbstractQuerySet(models.QuerySet):
    def dependency_permission(self, user):
        # model_name = self.model._meta.model_name
        model_name = 'task'
        company = user.company
        group = user.group
        view_all_slug = model_name + '_' + model_name + '-view-all'
        view_mine_slug = model_name + '_' + model_name + '-view'
        task_queryset = self.none()
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug=view_all_slug
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            task_queryset = self.filter(q_obj).exclude(status__in=[3, 4]).distinct('id')
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug=view_mine_slug
        ).exists():
            task_queryset = (
                self.filter(
                    Q(organization=company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                )
                .exclude(status__in=[3, 4])
                .distinct('id')
            )
        else:
            pass
        return task_queryset


class TaskAbstractManager(models.Manager):
    def get_queryset(self):
        return TaskAbstractQuerySet(self.model, using=self._db)


# We need to create a manager for task because of the usage of TaskAbstract in several models/views/helper very bad
class TaskAbstract(PFTCommonModel):
    """
    TaskAbstract model
    """

    STATUS_CHOICES = (
        (1, _("New")),
        (2, _("In-Progress")),
        (3, _("Completed")),
        (4, _("Archived")),
        (5, _("External Request")),
        (6, _("External Update")),
        (7, _("Advise")),
        (8, _("Analyze")),
        (9, _("Approve")),
        (10, _("Brief")),
        (11, _("Closing")),
        (12, _("Communicate")),
        (13, _("Coordinate")),
        (14, _("Deposition")),
        (15, _("Diligence")),
        (16, _("Discovery")),
        (17, _("Document")),
        (18, _("Draft")),
        (19, _("Execute")),
        (20, _("Fact Gathering")),
        (21, _("File")),
        (22, _("File Management")),
        (23, _("Hearing")),
        (24, _("Investigate")),
        (25, _("Negotiate")),
        (26, _("On Hold")),
        (27, _("Plan")),
        (28, _("Pleading")),
        (29, _("Prepare")),
        (30, _("Research")),
        (31, _("Review")),
        (32, _("Revise")),
        (33, _("Settle")),
        (34, _("Structure")),
    )
    assigned_to = models.ForeignKey(
        'authentication.User',
        verbose_name=_('Assigned To'),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(class)s_assigned_to_user',
    )
    observers = models.ManyToManyField(
        'authentication.User',
        blank=True,
        related_name='%(class)s_observers',
        verbose_name=_('Observers'),
    )

    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Task Priority'),
    )
    attachments = GenericRelation(
        'Attachment',
        object_id_field='object_id',
        content_type_field='content_type',
        related_query_name='%(app_label)s_%(class)s_content_object',
    )
    # tags = models.CharField(verbose_name=_('Tag'), max_length=254, )
    task_tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='%(class)s_tags',
        verbose_name=_('Task Tag'),
    )
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='%(class)s_organization',
        verbose_name=_('Company'),
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=1,
        verbose_name=_('Status'),
    )
    created_by = models.ForeignKey(
        'authentication.User',
        null=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_created_by',
        verbose_name=_('Created By'),
    )
    pre_save_data = JSONField(
        null=True,
        blank=True,
        help_text="Backend flag",
    )

    # Attorney Client privilege - TaskAbstract
    attorney_client_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Attorney Client",
    )
    # Work Product privilege - TaskAbstract
    work_product_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Work Product",
    )
    # Confidential privilege - TaskAbstract
    confidential_privilege = models.BooleanField(
        default=False,
        verbose_name="Task Privilege Confidential",
    )
    assigned_to_group = models.ManyToManyField(
        'WorkGroup',
        related_name='%(class)s_assigned_to_workgroup',
        blank=True,
        verbose_name=_('WorkGroup Task'),
    )
    requester = models.ForeignKey(
        'ServiceDesk',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_request',
        verbose_name=_('Request To Task'),
    )
    servicedesk_request = models.ForeignKey(
        'ServiceDeskRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='servicedesk_request_%(class)s',
        verbose_name=_('ServiceDeskRequest To Task'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Task Delete'),
    )
    prior_task = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_prior',
        verbose_name=_('Prior Task'),
    )
    after_task = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_after',
        verbose_name=_('After Task'),
    )
    task_template = models.ForeignKey(
        'TaskTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Task template'),
    )
    custom_fields_value = JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name=_('Custom fields value'),
    )

    objects = TaskAbstractManager()

    class Meta:
        abstract = True
        verbose_name = _('Task Abstract')
        verbose_name_plural = _('Tasks Abstract')

    def __str__(self):
        return str(self.name)

    def clean(self):
        self.custom_fields_value = self.prepare_custom_fields_value_task(self.task_template, self.custom_fields_value)
        self.clean_custom_fields_value(self.task_template, self.custom_fields_value)

    @classmethod
    def clean_custom_fields_value(cls, task_template, custom_fields_value, raise_error=True):
        if task_template and custom_fields_value:
            errors = []
            custom_fields_template_queryset = task_template.customfield_set.active()
            for cft in custom_fields_template_queryset:
                for item in custom_fields_value:
                    if str(item) == str(cft.pk):
                        e = cft.validate_value(custom_fields_value[item])
                        if e:
                            errors.append({f'{item}': e})
            if len(errors) > 0 and raise_error:
                raise ValidationError(
                    {
                        'custom_fields_value': errors,
                    }
                )
            return errors

    @classmethod
    def prepare_custom_fields_value_task(cls, task_template, custom_fields_value):
        """
        Add `id` custom field with value
        """
        if not task_template:
            return {}

        if not custom_fields_value:
            custom_fields_value = {}

        custom_fields_template_queryset = task_template.customfield_set.active()
        custom_fields_template = {}
        for item in custom_fields_template_queryset:
            custom_fields_template[str(item.pk)] = item.default_value
        custom_fields_template_pk = set(custom_fields_template.keys())
        custom_fields = set(custom_fields_value.keys())
        fields_must_add = custom_fields_template_pk - custom_fields
        fields_must_remove = custom_fields - custom_fields_template_pk
        for x in fields_must_add:
            custom_fields_value.update({x: custom_fields_template[x]})

        for x in fields_must_remove:
            custom_fields_value.pop(x, None)
        return custom_fields_value

    def save(self, *args, **kwargs):
        self.full_clean()
        super(TaskAbstract, self).save(*args, **kwargs)
