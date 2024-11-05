from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from base.db import BaseModel, BaseModelManager, BaseModelQuerySet
from .templatecustomfields import TemplateCustomField

IMPORTANCE_CHOICES = (
    (0, _("No importance")),
    (1, _("Low")),
    (2, _("Med")),
    (3, _("High")),
)


class BaseTemplateQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(BaseTemplateQueryset, self).__init__(*args, **kwargs)

    def active(self):
        return super(BaseTemplateQueryset, self).active().filter(is_delete=False)


class BaseTemplateManager(BaseModelManager):
    def get_queryset(self):
        return BaseTemplateQueryset(self.model, using=self._db)


class BaseTemplateModel(BaseModel):
    title = models.CharField(
        max_length=254,
        db_index=True,
        verbose_name=_('Title'),
    )
    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Name'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_created_by',
        verbose_name=_('Created By'),
    )
    importance = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        choices=IMPORTANCE_CHOICES,
        verbose_name=_('Priority'),
    )

    assigned_to_group = models.ManyToManyField(
        'projects.WorkGroup',
        related_name='%(app_label)s_%(class)s_assigned_to_workgroup',
        blank=True,
        verbose_name=_('WorkGroup'),
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
        blank=True,
        null=True,
        verbose_name=_('Description'),
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name=_('Is Private'),
    )
    # Attorney Client privilege
    attorney_client_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Privilege Attorney Client"),
    )
    # Work Product privilege
    work_product_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Privilege Work Product"),
    )
    # Confidential privilege
    confidential_privilege = models.BooleanField(
        default=False,
        verbose_name=_("Privilege Confidential"),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Template Delete'),
    )
    custom_fields = GenericRelation(TemplateCustomField)

    objects = BaseTemplateManager()

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.title)

    def clean(self):
        super(BaseTemplateModel, self).clean()
        if self.due_date and self.start_date and self.due_date < self.start_date:
            raise ValidationError({'due_date': _('Due date must be greater than start date')})
