import django_filters
from django_filters import rest_framework as DRFfilters

import django_filters as filters

from notifications.filters import MultiChoiceFilter

from projects.tasksapp.models import TaskTemplate


class TaskTemplateFilterSet(DRFfilters.FilterSet):
    created_by = MultiChoiceFilter(field_name='created_by_id')

    class Meta:
        model = TaskTemplate
        fields = []
