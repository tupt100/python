from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.dateparse import datetime_re, parse_datetime

from nmbl.apps.base.db import BaseModel, BaseModelManager, BaseModelQuerySet, TextChoices


class CustomFieldType(TextChoices):
    TEXT = 'Text', _('Text')
    NUMBER = 'Number', _('Number')
    DATE = 'Date', _('Date')
    CURRENCY = 'Currency', _('Currency')

    def validate(self, value) -> bool:
        """Check value can we cast to specific type?"""
        if self == CustomFieldType.TEXT:
            method = str
        elif self == CustomFieldType.NUMBER:
            method = int
        elif self == CustomFieldType.DATE:
            method = lambda x: (_ for _ in ()).throw(Exception('Datetime validation')) if not datetime_re.match(
                x) else parse_datetime(x)
        elif self == CustomFieldType.CURRENCY:
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


class CustomFieldQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(CustomFieldQueryset, self).__init__(*args, **kwargs)


class CustomFieldManager(BaseModelManager):
    def get_queryset(self):
        return CustomFieldQueryset(self.model, using=self._db)


class CustomField(BaseModel):
    task_template = models.ForeignKey(
        'projects.TaskTemplate',
        on_delete=models.PROTECT,
        verbose_name=_('Task template'),
    )
    label = models.CharField(
        max_length=40,
        null=False,
        blank=False,
        verbose_name=_('Label')
    )
    field_type = models.CharField(
        max_length=10,
        choices=CustomFieldType.choices,
        default=CustomFieldType.TEXT,
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

    objects = CustomFieldManager()

    class Meta:
        verbose_name = _('Custom field')
        verbose_name_plural = _('Custom fields')

    def __str__(self):
        return '{}'.format(self.label)

    def clean(self):
        custom_field_type = CustomFieldType(self.field_type)
        if self.default_value and not custom_field_type.validate(self.default_value):
            raise ValidationError({
                'default_value': [
                    _('Default value type does not match with current type "%(field_type)s".') % {
                        'field_type': custom_field_type,
                    }
                ]
            })

    def validate_value(self, value):
        custom_field_type = CustomFieldType(self.field_type)
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
