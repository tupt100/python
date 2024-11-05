from django_filters import rest_framework as DRFfilters
import django_filters as filters
from ...models import ProjectTemplate, TemplateCustomField, TemplateCustomFieldType
from projects.models import GlobalCustomFieldAllowedType
from notifications.filters import MultiChoiceFilter


class TemplateCustomFieldFilterSet(DRFfilters.FilterSet):
    # TODO: fix
    object_id = MultiChoiceFilter(field_name='object_id')

    content_type = filters.MultipleChoiceFilter(
        field_name='content_type',
        choices=GlobalCustomFieldAllowedType.choices,
        method='allow_content_type_filter'
    )

    field_type = filters.MultipleChoiceFilter(
        field_name='field_type',
        choices=TemplateCustomFieldType.choices,
        widget=filters.fields.CSVWidget,
    )

    class Meta:
        model = TemplateCustomField
        fields = []
