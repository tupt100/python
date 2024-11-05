from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils.dateparse import datetime_re, parse_datetime
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from base.db import BaseModel, BaseModelManager, BaseModelQuerySet, TextChoices


class TemplateCustomFieldType(TextChoices):
    TEXT = 'Text', _('Text')
    NUMBER = 'Number', _('Number')
    DATE = 'Date', _('Date')
    CURRENCY = 'Currency', _('Currency')

    def validate(self, value) -> bool:
        """Check value can we cast to specific type?"""
        if self == TemplateCustomFieldType.TEXT:
            method = str
        elif self == TemplateCustomFieldType.NUMBER:
            method = int
        elif self == TemplateCustomFieldType.DATE:
            method = lambda x: (_ for _ in ()).throw(Exception('Datetime validation')) if not datetime_re.match(
                x) else parse_datetime(x)
        elif self == TemplateCustomFieldType.CURRENCY:
            method = lambda x: "{:.2f}".format(float(x))
        else:
            return False
        try:
            _ = self._cast_with_type(method, value)
            return True
        except ValueError:
            return False
        except Exception:
            return False

    @staticmethod
    def _cast_with_type(cast_type, value):
        return cast_type(value)


class TemplateCustomFieldQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(TemplateCustomFieldQueryset, self).__init__(*args, **kwargs)


class TemplateCustomFieldManager(BaseModelManager):
    def get_queryset(self):
        return TemplateCustomFieldQueryset(self.model, using=self._db)


class TemplateCustomField(BaseModel):
    label = models.CharField(
        max_length=40,
        null=False,
        blank=False,
        verbose_name=_('Label')
    )
    field_type = models.CharField(
        max_length=10,
        choices=TemplateCustomFieldType.choices,
        default=TemplateCustomFieldType.TEXT,
        verbose_name=_('Type')
    )
    default_value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Default value')
    )
    is_required = models.BooleanField(
        null=False,
        blank=False,
        verbose_name=_('Is required?')
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Description')
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Object id')
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=(
                Q(app_label='projects', model='projecttemplate') |
                Q(app_label='projects', model='workflowtemplate')
        ),
        null=True,
        blank=True,
        verbose_name=_('Content Type')
    )
    content_object = GenericForeignKey(
        ct_field='content_type',
        fk_field='object_id',
    )

    objects = TemplateCustomFieldManager()

    class Meta:
        verbose_name = _('Template custom field')
        verbose_name_plural = _('Template custom fields')

    def __str__(self):
        return '{}'.format(self.label)

    def clean(self):
        custom_field_type = TemplateCustomFieldType(self.field_type)
        if self.default_value and not custom_field_type.validate(self.default_value):
            raise ValidationError({
                'default_value': [
                    _('Default value type does not match with current type "%(field_type)s".') % {
                        'field_type': custom_field_type,
                    }
                ]
            })

    def validate_value(self, value):
        custom_field_type = TemplateCustomFieldType(self.field_type)
        if value and not custom_field_type.validate(value):
            return ValidationError(
                [
                    _('Default value type does not match with current type "%(field_type)s".') % {
                        'field_type': custom_field_type,
                    }
                ]
            )
        if not value and self.is_required:
            return ValidationError(
                [
                    _('This is field is required')
                ]
            )

