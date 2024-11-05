from django_filters import rest_framework as DRFfilters
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

import django_filters as filters
from django.contrib.contenttypes.models import ContentType

from ...models import GlobalCustomFieldValueType, GlobalCustomFieldAllowedType
from notifications.filters import MultiChoiceFilter


class GlobalCustomFieldFilterSet(DRFfilters.FilterSet):
    field_type = filters.MultipleChoiceFilter(
        field_name='field_type',
        choices=GlobalCustomFieldValueType.choices,
        widget=filters.fields.CSVWidget,
    )
    created_by = MultiChoiceFilter(field_name='created_by_id')
    allow_content_type = filters.MultipleChoiceFilter(
        field_name='allow_content_type',
        choices=GlobalCustomFieldAllowedType.choices,
        method='allow_content_type_filter'
    )


    def allow_content_type_filter(self, queryset, name, value):
        content_type = [GlobalCustomFieldAllowedType.get_content_type_value(item) for item in value]
        not_allowed_content_type = set(content_type) - set(GlobalCustomFieldAllowedType.content_type_values)
        if not_allowed_content_type:
            raise ValidationError({
                'allow_content_type': [
                    _(f'Allow content type filter is not valid, you have to choice one of ({GlobalCustomFieldAllowedType.choices})')
                ]
            })
        return queryset.filter(allow_content_type__contains=content_type)
