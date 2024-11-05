from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models, connection
from django.utils.dateparse import datetime_re, parse_datetime
from django.utils.translation import gettext_lazy as _

from base.db import BaseModel, BaseModelManager, BaseModelQuerySet, TextChoices, ChoicesMeta


class GlobalChoicesMeta(ChoicesMeta):
    @staticmethod
    def _pair_content_type_id(cls):
        try:
            result = tuple(ContentType.objects.filter(model__in=cls.values).values_list('pk', 'model'))
        except:
            result = tuple(('pk', 'model'))
        return result

    def __new__(metacls, classname, bases, classdict):
        cls = super(GlobalChoicesMeta, metacls).__new__(metacls, classname, bases, classdict)
        cls._content_types_with_schema = {}
        return cls

    @property
    def _content_types(self):
        key = self._schema
        return self._content_types_with_schema.get(key) or self._content_types_with_schema.setdefault(
            key,
            GlobalChoicesMeta._pair_content_type_id(self),
        )

    @property
    def _schema(self):
        return connection.get_schema()

    @property
    def choices_content_type(self):
        return self._content_types

    @property
    def content_type_values(self):
        return [value for value, _ in self.choices_content_type]

    def get_content_type_model(self, value):
        for pk, content_type in self._content_types:
            if pk == value:
                return content_type
        return None

    def get_content_type_value(self, model):
        for pk, content_type in self._content_types:
            if content_type == model.lower():
                return pk
        return None


class GlobalCustomFieldAllowedType(TextChoices, metaclass=GlobalChoicesMeta):
    PROJECT = _('project'), _('Project')
    TASK = _('task'), _('Task')
    WORKFLOW = _('workflow'), _('Workflow')


class GlobalCustomFieldValueType(TextChoices):
    TEXT = 'Text', _('Text')
    NUMBER = 'Number', _('Number')
    DATE = 'Date', _('Date')
    CURRENCY = 'Currency', _('Currency')

    def validate(self, value) -> bool:
        """Check value can we cast to specific type?"""
        if self == GlobalCustomFieldValueType.TEXT:
            method = str
        elif self == GlobalCustomFieldValueType.NUMBER:
            method = int
        elif self == GlobalCustomFieldValueType.DATE:
            method = lambda x: (_ for _ in ()).throw(Exception('Datetime validation')) if not datetime_re.match(
                x) else parse_datetime(x)
        elif self == GlobalCustomFieldValueType.CURRENCY:
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


class GlobalCustomFieldQueryset(BaseModelQuerySet):
    def __init__(self, *args, **kwargs):
        super(GlobalCustomFieldQueryset, self).__init__(*args, **kwargs)

    def active(self):
        return super(GlobalCustomFieldQueryset, self).active().filter(is_archive=False)


class GlobalCustomFieldManager(BaseModelManager):
    def get_queryset(self):
        return GlobalCustomFieldQueryset(self.model, using=self._db)


class GlobalCustomField(BaseModel):
    label = models.CharField(
        max_length=40,
        null=False,
        blank=False,
        verbose_name=_('Label')
    )
    field_type = models.CharField(
        max_length=10,
        choices=GlobalCustomFieldValueType.choices,
        default=GlobalCustomFieldValueType.TEXT,
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
    is_archive = models.BooleanField(
        verbose_name=_('Is archive'),
        null=False,
        blank=False,
        default=False
    )

    allow_content_type = JSONField(
        default=list,
        null=False,
        blank=False,
        verbose_name=_('Allow content type'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
        verbose_name=_('Created By'),
    )

    objects = GlobalCustomFieldManager()

    class Meta:
        verbose_name = _('Global custom filed')
        verbose_name_plural = _('Global custom fields')

    def __str__(self):
        return '{}'.format(self.label)

    def clean(self):
        global_custom_field_type = GlobalCustomFieldValueType(self.field_type)
        self.clean_allow_contents_type(self.allow_content_type)
        if self.default_value and not global_custom_field_type.validate(self.default_value):
            raise ValidationError({
                'default_value': [
                    _('Default value type does not match with current type "%(field_type)s".') % {
                        'field_type': global_custom_field_type,
                    }
                ]
            })

    @classmethod
    def clean_allow_contents_type(cls, allow_content_type, raise_error=True):
        errors = []
        compare_allow_list = set(list(map(int, allow_content_type))) - set(
            GlobalCustomFieldAllowedType.content_type_values)

        for content_type in compare_allow_list:
            errors.append(
                ValidationError(
                    [
                        _('Content Type is not valid "%(content_type)s".') % {
                            'content_type': content_type,
                        }
                    ]
                )
            )

        if not allow_content_type:
            errors.append(
                ValidationError(
                    [
                        _('This field is required')
                    ]
                )
            )
        if len(errors) > 0 and raise_error:
            raise ValidationError({
                'allow_content_type': errors,
            })
        return errors

    def validate_value(self, value):
        global_custom_field_type = GlobalCustomFieldValueType(self.field_type)
        if value and not global_custom_field_type.validate(value):
            return ValidationError(
                [
                    _('Default value type does not match with current type "%(field_type)s".') % {
                        'field_type': global_custom_field_type,
                    }
                ]
            )
        if not value and self.is_required:
            return ValidationError(
                [
                    _('This is field is required')
                ]
            )
