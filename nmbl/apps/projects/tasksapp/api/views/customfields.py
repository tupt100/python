from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

from nmbl.apps.base.api.views import BaseModelViewSet
from projects.tasksapp.api.serializers import CustomFieldDetailSerializer

from projects.tasksapp.models import CustomField

from projects.tasksapp.api.permissions import CustomFieldTaskTemplateOwner

from projects.tasksapp.api.filters import CustomFieldFilterSet

"""
CustomField
"""


class CustomFieldViewSet(BaseModelViewSet):
    """
    list:
    API to list all Custom in task template

    * Filter custom field by type
    ```
    Field type values ==> Text: Text, Number: Number
    To filter custom field by text type > field_type=Text
    To filter custom field by text & number type > field_type=Text,Number
    ```
    * Filter custom field by task template
    ```
    To filter custom field by task template > task_template_id=1
    To filter custom field by task template > task_template_id=1,2
    ```

    create:
    API to create new custom field

    * custom field `label`, `task_template_id`, `field_type` and `is_required`  is required filed.
    * You can set default value of custom field `default_value`
    * Field type values ==> Text: Text, Number: Number
    * Is required values ==> false, true
    * `task_template_id`: Id of task template
    * `label`: label of custom field
    * `description`: hint for field

    """
    queryset = CustomField.objects.none()
    model = CustomField
    serializers = {
        'default': CustomFieldDetailSerializer,
    }
    filterset_class = CustomFieldFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
    ]
    ordering_fields = []
    search_fields = []
    permission_classes_by_action = {
        'default': [CustomFieldTaskTemplateOwner, ],
        'list': [IsAuthenticated, ],
        'retrieve': [IsAuthenticated, ],
        'create': [CustomFieldTaskTemplateOwner, ],
        'update': [CustomFieldTaskTemplateOwner, ],
        'destroy': [CustomFieldTaskTemplateOwner, ],
    }
