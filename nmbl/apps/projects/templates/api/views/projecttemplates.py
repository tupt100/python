from django_filters import rest_framework as filters
from projects.tasksapp.api.permissions import DenyAny
from rest_framework.filters import OrderingFilter, SearchFilter

from ...models import ProjectTemplate
from ..filters import ProjectTemplateFilterSet
from ..permissions import (
    ProjectTemplateCreatePermission,
    ProjectTemplateDestroyPermission,
    ProjectTemplateUpdatePermission,
    ProjectTemplateViewPermission,
)
from ..serializers import (
    ProjectTemplateDetailSerializerSummarySerializer,
    ProjectTemplateSummarySerializer,
)
from .basetemplates import BaseTemplateViewSet

"""
ProjectTemplate
"""


class ProjectTemplateViewSet(BaseTemplateViewSet):
    """
    list:
    API to list all project template

    * API to filter project template by who create the project template
    ```
    To filter project template by who created project template > created_by=1
    To filter project template by user with 1 and user with id 3 > created_by=1,3
    ```

    * Sort project template by fields
    ```
    To sort project template by any field pass that field name in ordering
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
    API to create new project template

    * project template `name` is required filed.

    """

    queryset = ProjectTemplate.objects.none()
    model = ProjectTemplate
    serializers = {
        'default': ProjectTemplateSummarySerializer,
        'retrieve': ProjectTemplateDetailSerializerSummarySerializer,
        'list': ProjectTemplateSummarySerializer,
        'create': ProjectTemplateDetailSerializerSummarySerializer,
        'update': ProjectTemplateDetailSerializerSummarySerializer,
    }

    permission_classes_by_action = {
        'default': [
            DenyAny,
        ],
        'list': [
            ProjectTemplateViewPermission,
        ],
        'retrieve': [
            ProjectTemplateViewPermission,
        ],
        'create': [
            ProjectTemplateCreatePermission,
        ],
        'update': [
            ProjectTemplateUpdatePermission,
        ],
        'destroy': [
            ProjectTemplateDestroyPermission,
        ],
    }
    filterset_class = ProjectTemplateFilterSet
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
            )
            .prefetch_related('assigned_to_users', 'assigned_to_group', 'custom_fields')
        )
