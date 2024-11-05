from django_filters import rest_framework as filters
from django.contrib.contenttypes.models import ContentType

from rest_framework import status
from rest_framework.response import Response

from base.api.views import BaseModelViewSet
from ...models import GlobalCustomField
from ..serializers import GlobalCustomFieldDetailSerializer
from ..filters import GlobalCustomFieldFilterSet
from ....tasksapp.api.permissions import DenyAny

from ..permissions import (GlobalCustomFieldViewPermission,
                           GlobalCustomFieldCreatePermission,
                           GlobalCustomFieldUpdatePermission,
                           GlobalCustomFieldDestroyPermission,
                           GlobalCustomFieldOwner)

"""
GlobalCustomField
"""


class GlobalCustomFieldViewSet(BaseModelViewSet):
    """
    list:
    API to list all global custom fields

    * Filter global custom field by type
    ```
    Field type values ==> Text: Text, Number: Number
    To filter global custom field by text type > field_type=Text
    To filter global custom field by text & number type > field_type=Text,Number
    ```

    * API to filter global custom field by who create the task template
    ```
    To filter global custom field by who created task template > created_by=1
    To filter global custom field by user with 1 and user with id 3 > created_by=1,3
    ```

    * Filter global custom field by allow content type
    ```
    Allow content type values ==> project: Project, task: Task, workflow: Workflow
    To filter allow content type field by Task > allow_content_type=task
    ```


    create:
    API to create new global custom field

    * global custom field `label`, `field_type`, `allow_content_type` and `is_required`  is required filed.
    * `label`: label of custom field
    * Field type values ==> Text: Text, Number: Number
    * Allow content type values ==>  [Project: project, Task: task, Workflow: workflow]
        for example "allow_content_type": ["task","project"]
    * Is required values ==> false, true
    * Is archive values ==> false, true
        for example `is_archive`: false
    * `description`: hint for field

    """
    queryset = GlobalCustomField.objects.none()
    model = GlobalCustomField
    serializers = {
        'default': GlobalCustomFieldDetailSerializer,
    }
    filterset_class = GlobalCustomFieldFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
    ]
    ordering_fields = []
    search_fields = []
    permission_classes_by_action = {
        'default': [DenyAny, ],
        'list': [GlobalCustomFieldViewPermission, ],
        'retrieve': [GlobalCustomFieldViewPermission, ],
        'create': [GlobalCustomFieldCreatePermission, ],
        'update': [GlobalCustomFieldUpdatePermission, ],
        'destroy': [GlobalCustomFieldDestroyPermission, ],
    }

    def perform_create(self, serializer, **kwargs):
        user = self.request.user.id
        kwargs['created_by_id'] = user
        super(GlobalCustomFieldViewSet, self).perform_create(serializer=serializer, **kwargs)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        item.is_archive = True
        item.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
