from django_filters import rest_framework as filters
from projects.tasksapp.api.permissions import DenyAny
from rest_framework.filters import OrderingFilter, SearchFilter

from ...models import WorkflowTemplate
from ..filters import WorkflowTemplateFilterSet
from ..permissions import (
    WorkflowTemplateCreatePermission,
    WorkflowTemplateDestroyPermission,
    WorkflowTemplateUpdatePermission,
    WorkflowTemplateViewPermission,
)
from ..serializers import (
    WorkflowTemplateDetailSerializerSummarySerializer,
    WorkflowTemplateSummarySerializer,
)
from .basetemplates import BaseTemplateViewSet

"""
WorkflowTemplate
"""


class WorkflowTemplateViewSet(BaseTemplateViewSet):
    """
    list:
    API to list all workflow template

    * API to filter workflow template by who create the workflow template
    ```
    To filter workflow template by who created workflow template > created_by=1
    To filter workflow template by user with 1 and user with id 3 > created_by=1,3
    ```

    * Sort workflow template by fields
    ```
    To sort workflow template by any field pass that field name in ordering
    Sorting fields: 'name', 'created_by', 'pk', 'created_at', 'update_at'
    e.g : ascending by title > ordering=name
         descending by title > ordering=-name
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
    API to create new workflow template

    * workflow template `name` is required filed.

    """

    queryset = WorkflowTemplate.objects.none()
    model = WorkflowTemplate
    serializers = {
        'default': WorkflowTemplateSummarySerializer,
        'retrieve': WorkflowTemplateDetailSerializerSummarySerializer,
        'list': WorkflowTemplateSummarySerializer,
        'create': WorkflowTemplateDetailSerializerSummarySerializer,
        'update': WorkflowTemplateDetailSerializerSummarySerializer,
    }

    permission_classes_by_action = {
        'default': [
            DenyAny,
        ],
        'list': [
            WorkflowTemplateViewPermission,
        ],
        'retrieve': [
            WorkflowTemplateViewPermission,
        ],
        'create': [
            WorkflowTemplateCreatePermission,
        ],
        'update': [
            WorkflowTemplateUpdatePermission,
        ],
        'destroy': [
            WorkflowTemplateDestroyPermission,
        ],
    }
    filterset_class = WorkflowTemplateFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    ]
    ordering_fields = [
        'name',
        'created_by',
        'created_at',
        'update_at',
    ]
    search_fields = [
        'name',
        'title',
        'description',
    ]

    def get_queryset(self):
        return (
            self.model.objects.active()
            .select_related(
                'created_by',
                'project',
            )
            .prefetch_related('assigned_to_users', 'assigned_to_group', 'custom_fields')
        )
