from django_filters import rest_framework as DRFfilters
import django_filters as filters
from authentication.models import User


class ProjectTemplateFilterSet(DRFfilters.FilterSet):
    created_by = filters.ModelMultipleChoiceFilter(
        field_name='created_by_id',
        queryset=User.objects.all()
    )
