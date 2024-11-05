from django_filters import rest_framework as filters

from .models import Notification


class MultiChoiceFilter(filters.Filter):
    """
    Filter class for multiple values separated by comma
    """

    def filter(self, qs, value):
        if not value:
            return qs

        values = [int(x) for x in value.split(',') if x.strip().isdigit()]
        lookup = self.field_name + '__in'
        qs = qs.filter(**{lookup: values}).distinct()
        return qs


class NotificationFilterSet(filters.FilterSet):
    status = MultiChoiceFilter(field_name='status')

    class Meta:
        model = Notification
        fields = []
