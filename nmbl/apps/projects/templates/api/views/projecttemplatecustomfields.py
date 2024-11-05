from django.contrib.contenttypes.models import ContentType
from django_filters import rest_framework as filters
from rest_framework.permissions import IsAuthenticated

from ...models import ProjectTemplate, TemplateCustomField
from ..filters import TemplateCustomFieldFilterSet
from ..permissions import CustomFieldProjectTemplateOwner
from ..serializers import TemplateCustomFieldSummarySerializer
from .templatecustomfields import TemplateCustomFieldViewSet

"""
ProjectTemplateCustomField
"""


class ProjectTemplateCustomFieldViewSet(TemplateCustomFieldViewSet):
    """
    list:
    API to list all Custom in Project template

    * Filter custom field by type
    ```
    Field type values ==> Text: Text, Int: Int
    To filter custom field by text type > field_type=Text
    To filter custom field by text & int type > field_type=Text,Int
    ```
    * Filter custom field by Project template
    ```
    To filter custom field by Project template > template_id=1
    To filter custom field by Project template > template_id=1,2
    ```

    create:
    API to create new custom field

    * custom field `label`, `template_id`, `field_type` and `is_required`  is required filed.
    * You can set default value of custom field `default_value`
    * Field type values ==> Text: Text, Int: Int
    * Is required values ==> false, true
    * `template_id`: Id of Project template
    * `label`: label of custom field
    * `description`: hint for field

    """

    queryset = TemplateCustomField.objects.none()
    model = TemplateCustomField
    serializers = {
        'default': TemplateCustomFieldSummarySerializer,
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
        content_type_model = ContentType.objects.get_for_model(ProjectTemplate)
        return self.model.objects.active().filter(content_type=content_type_model)

    def perform_create(self, serializer, **kwargs):
        content_type_model = ContentType.objects.get_for_model(ProjectTemplate)
        kwargs['content_type'] = content_type_model
        super(ProjectTemplateCustomFieldViewSet, self).perform_create(serializer=serializer, **kwargs)
