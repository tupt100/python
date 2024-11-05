from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomFieldValueMixin(models.Model):
    custom_fields_value = JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name=_('Custom fields value'),
    )

    class Meta:
        abstract = True

    """
    You should call this method on clean method:
    ```
    def clean(self):
        self.custom_fields_value = self.prepare_custom_fields_value(self.workflow_template,
                                                                             self.custom_fields_value)
        self.clean_custom_fields_value(self.workflow_template, self.custom_fields_value)
    ```
    """

    @classmethod
    def clean_custom_fields_value(cls, template, custom_fields_value, raise_error=True):
        if template and custom_fields_value:
            errors = []
            custom_fields_template_queryset = template.custom_fields.active()
            for cft in custom_fields_template_queryset:
                for item in custom_fields_value:
                    if str(item) == str(cft.pk):
                        e = cft.validate_value(custom_fields_value[item])
                        if e:
                            errors.append({f'{item}': e})
            if len(errors) > 0 and raise_error:
                raise ValidationError({
                    'custom_fields_value': errors,
                })
            return errors

    @classmethod
    def prepare_custom_fields_value(cls, template, custom_fields_value):
        """
        Add `id` custom field with value
        """
        if not template:
            return {}

        if not custom_fields_value:
            custom_fields_value = {}

        custom_fields_template_queryset = template.custom_fields.active()
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
