from django_filters import rest_framework as filters
from .models import Group


class GroupFilterSet(filters.FilterSet):
    is_user_specific = filters.BooleanFilter(field_name='is_user_specific')
    is_public = filters.BooleanFilter(field_name='is_public')

    class Meta:
        model = Group
        fields = []
