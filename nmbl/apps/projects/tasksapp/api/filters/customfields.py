import django_filters
from django_filters import rest_framework as DRFfilters

import django_filters as filters

from notifications.filters import MultiChoiceFilter

from projects.tasksapp.models import CustomField

from projects.tasksapp.models import CustomFieldType


class CustomFieldFilterSet(DRFfilters.FilterSet):
    task_template_id = MultiChoiceFilter(field_name='task_template_id')
    field_type = filters.MultipleChoiceFilter(
        field_name='field_type',
        choices=CustomFieldType.choices,
        widget=filters.fields.CSVWidget,
    )

    class Meta:
        model = CustomField
        fields = []
