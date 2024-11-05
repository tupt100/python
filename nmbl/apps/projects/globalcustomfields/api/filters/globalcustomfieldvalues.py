from django_filters import rest_framework as DRFfilters
import django_filters as filters
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from notifications.filters import MultiChoiceFilter
from ...models import GlobalCustomFieldAllowedType, GlobalCustomField


class GlobalCustomFieldValueFilterSet(DRFfilters.FilterSet):
    global_custom_field = filters.ModelMultipleChoiceFilter(
        field_name='global_custom_field_id',
        queryset=GlobalCustomField.objects.all()
    )

    object_id = MultiChoiceFilter(field_name='object_id')

    content_type = filters.MultipleChoiceFilter(
        field_name='content_type',
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
        return queryset.filter(content_type_id__in=content_type)
