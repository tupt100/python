from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models.functions import Upper

from .globalcustomfields import GlobalCustomFieldValueType
from base.db import BaseModel, BaseModelManager, BaseModelQuerySet, TextChoices


class GlobalCustomFieldValueQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(GlobalCustomFieldValueQueryset, self).__init__(*args, **kwargs)

    def active(self):
        return super(GlobalCustomFieldValueQueryset, self).active().filter(is_archive=False)


class GlobalCustomFieldValueManager(BaseModelManager):
    def get_queryset(self):
        return GlobalCustomFieldValueQueryset(self.model, using=self._db)


class GlobalCustomFieldValue(BaseModel):
    global_custom_field = models.ForeignKey(
        'projects.GlobalCustomField',
        on_delete=models.PROTECT,
        verbose_name=_('Global custom field')
    )
    value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Value')
    )
    is_archive = models.BooleanField(
        verbose_name=_('Is archive'),
        default=False,
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Object id')
    )
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        verbose_name=_('Content type'),
    )
    content_object = GenericForeignKey(
        ct_field='content_type',
        fk_field='object_id'
    )

    objects = GlobalCustomFieldValueManager()

    class Meta:
        verbose_name = _('Global custom field value')
        verbose_name_plural = _('Global custom field values')

    def clean(self):
        if self.content_type_id not in map(int, self.global_custom_field.allow_content_type):
            raise ValidationError({
                'content_type': [
                    _('Content type is not valid you have to choice "%(content_types)s".') % {
                        'content_types': tuple(ContentType.objects.filter(
                            pk__in=self.global_custom_field.allow_content_type).values_list('model', Upper('model'))),
                    }

                ]
            })

        if not self.content_type.model_class().objects.filter(pk=self.object_id).exists():
            raise ValidationError({
                'object_id': [
                    _(f'Related Object id is not valid.')
                    # _('Related Object id is not valid. Type ID: %(type_id)d Type: %(content_type)s ID: %(object_id)d') % {
                    #     'type_id': self.content_type_id,
                    #     'content_type': self.content_type,
                    #     'object_id': self.object_id
                    # }
                ]
            })
        if self.validate_value(value=self.value):
            raise self.validate_value(value=self.value)

    def validate_value(self, value):
        global_custom_field_type = GlobalCustomFieldValueType(self.global_custom_field.field_type)
        if value and not global_custom_field_type.validate(value):
            return ValidationError({
                'value': [
                    _('Value type does not match with current type "%(field_type)s".') % {
                        'field_type': global_custom_field_type,
                    }
                ]}
            )
        if not value and self.global_custom_field.is_required:
            return ValidationError({
                'value': [
                    _('This is field is required')
                ]}
            )
