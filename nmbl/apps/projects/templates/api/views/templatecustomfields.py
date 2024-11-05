from base.api.views import BaseModelViewSet
from django_filters import rest_framework as filters
from rest_framework.permissions import IsAuthenticated

from ...models import TemplateCustomField
from ..filters import TemplateCustomFieldFilterSet
from ..permissions import CustomFieldProjectTemplateOwner
from ..serializers import (
    TemplateCustomFieldDetailSerializer,
    TemplateCustomFieldSummarySerializer,
)

"""
TemplateCustomField
"""


class TemplateCustomFieldViewSet(BaseModelViewSet):
    """
    list:
    API to list all Custom in project template

    * Filter custom field by type
    ```
    Field type values ==> Text: Text, Int: Int
    To filter custom field by text type > field_type=Text
    To filter custom field by text & int type > field_type=Text,Int
    ```
    * Filter custom field by project template
    ```
    To filter custom field by project template > template_id=1
    To filter custom field by project template > template_id=1,2
    ```

    create:
    API to create new custom field

    * custom field `label`, `template_id`, `field_type` and `is_required`  is required filed.
    * You can set default value of custom field `default_value`
    * Field type values ==> Text: Text, Int: Int
    * Is required values ==> false, true
    * `template_id`: Id of project template
    * `label`: label of custom field
    * `description`: hint for field

    """

    queryset = TemplateCustomField.objects.none()
    model = TemplateCustomField
    serializers = {
        'default': TemplateCustomFieldSummarySerializer,
        'list': TemplateCustomFieldSummarySerializer,
        'retrieve': TemplateCustomFieldDetailSerializer,
        'create': TemplateCustomFieldDetailSerializer,
        'update': TemplateCustomFieldDetailSerializer,
    }
    filterset_class = TemplateCustomFieldFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
    ]
    ordering_fields = []
    search_fields = [
        'label',
        'description',
    ]
    permission_classes_by_action = {
        'default': [
            CustomFieldProjectTemplateOwner,
        ],
        'list': [
            IsAuthenticated,
        ],
        'retrieve': [
            IsAuthenticated,
        ],
        'create': [
            CustomFieldProjectTemplateOwner,
        ],
        'update': [
            CustomFieldProjectTemplateOwner,
        ],
        'destroy': [
            CustomFieldProjectTemplateOwner,
        ],
    }

    def get_queryset(self):
        raise NotImplementedError
