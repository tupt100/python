from django_filters import rest_framework as filters
from projects.models import TaskTemplate
from projects.tasksapp.api.serializers import TaskTemplateDetailSerializer
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from nmbl.apps.base.api.views import BaseModelViewSet

from ..filters import TaskTemplateFilterSet
from ..permissions import (
    DenyAny,
    TaskTemplateCreatePermission,
    TaskTemplateDestroyPermission,
    TaskTemplateUpdatePermission,
    TaskTemplateViewPermission,
)

"""
TaskTemplate
"""


class TaskTemplateViewSet(BaseModelViewSet):
    """
    list:
    API to list all task template

    * API to filter task template by who create the task template
    ```
    To filter task template by who created task template > created_by=1
    To filter task template by user with 1 and user with id 3 > created_by=1,3
    ```

    * Sort Task template by fields
    ```
    To sort task template by any field pass that field name in ordering
    Sorting fields: 'title', 'created_by', 'pk', 'created_at', 'update_at'
    e.g : ascending by title > ordering=title
         descending by title > ordering=-title
    ```

    * search API
    ```
    call this API :- ?search=search_data
    (any one parameter is required either search or tags)
    pass text that you want to search from entire database
    it will get you list where "codal" exist from
        entire database as a group by separate tables
    ```

    create:
    API to create new task template

    * task template `title` is required filed.

    * add custom fields in task template
    ```
    To add custom fields in task template call api create custom fields.
    ```
    """

    queryset = TaskTemplate.objects.none()
    model = TaskTemplate
    serializers = {
        'default': TaskTemplateDetailSerializer,
    }

    permission_classes_by_action = {
        'default': [
            DenyAny,
        ],
        'list': [
            TaskTemplateViewPermission,
        ],
        'retrieve': [
            TaskTemplateViewPermission,
        ],
        'create': [
            TaskTemplateCreatePermission,
        ],
        'update': [
            TaskTemplateUpdatePermission,
        ],
        'destroy': [
            TaskTemplateDestroyPermission,
        ],
    }
    filterset_class = TaskTemplateFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    ]
    ordering_fields = [
        'title',
        'created_by',
        'created_at',
        'update_at',
    ]
    search_fields = [
        'title',
        'task_name',
        'description',
    ]

    def perform_create(self, serializer, **kwargs):
        user = self.request.user
        kwargs['created_by_id'] = user.pk
        super(TaskTemplateViewSet, self).perform_create(serializer=serializer, **kwargs)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        item.is_delete = True
        item.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
