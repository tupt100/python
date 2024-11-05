from django.db import models, connection
from django.utils.translation import gettext_lazy as _

from nmbl.apps.base.db import BaseModel, BaseModelManager, BaseModelQuerySet, TextChoices


class FeatureName(TextChoices):
    """
    In some cases it's related to PERMISSION_CATEGORY_CHOICES. so, you must use it as the same name use category but camelcase.
    """
    EXTERNAL_DOCS = 'EXTERNAL_DOCS', _('External docs')
    TASK_TEMPLATE = 'TASKTEMPLATE', _('Task template')
    GLOBAL_CUSTOM_FIELD = 'GLOBALCUSTOMFIELD', _('Global custom field')
    WORKFLOW_TEMPLATE = 'WORKFLOWTEMPLATE', _('Workflow template')
    PROJECT_TEMPLATE = 'PROJECTTEMPLATE', _('Project template')


class FeatureQuerySet(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(FeatureQuerySet, self).__init__(*args, **kwargs)

    def active(self):
        return super(FeatureQuerySet, self).active().filter(client__schema_name=connection.schema_name)


class FeatureManager(BaseModelManager):
    def get_queryset(self):
        return FeatureQuerySet(self.model, using=self._db)


class Feature(BaseModel):
    client = models.ForeignKey(
        'customers.Client',
        on_delete=models.CASCADE,
        verbose_name=_('Client')
    )
    key = models.CharField(
        max_length=255,
        choices=FeatureName.choices,
        verbose_name=_('Feature')
    )
    value = models.BooleanField(
        default=False,
        verbose_name=_('Is Active?')
    )

    objects = FeatureManager()

    class Meta:
        unique_together = (('client', 'key'),)
        verbose_name = _('Feature')
        verbose_name_plural = _('Feature')
