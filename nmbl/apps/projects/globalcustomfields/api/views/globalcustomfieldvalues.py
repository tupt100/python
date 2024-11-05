from django_filters import rest_framework as filters
from django.contrib.contenttypes.models import ContentType

from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action

from base.api.views import BaseModelViewSet
from ...models import GlobalCustomFieldValue
from ..serializers import GlobalCustomFieldValueDetailSerializer

from ..filters import GlobalCustomFieldValueFilterSet

from ..permissions import GlobalCustomFieldOwner

"""
GlobalCustomFieldValue
"""


class GlobalCustomFieldValueViewSet(BaseModelViewSet):
    """
    list:
    API to list all global custom field values

    * Filter global custom field value by global_custom_field, object_id and content_type

    * API to filter global custom field value by global custom field
    ```
    To filter global custom field value by global custom field > global_custom_field=1
    ```

    ```
    Field object_id values ==> 1,2....
    To filter global custom field value by 1 object_id > object_id=1
    ```
    ```
    Field content_type values ==> Project: project, Task: task, Workflow: workflow
    To filter global custom field value by Task content type > content_type=Task
    ```


    create:
    API to create new global custom field value

    * global custom field `global_custom_field_id`, `value`, `object_id` and `content_type`  is required filed.
    * `global_custom_field_id`: Id of global custom field
    * `object_id`: id of content type object
    * `content_type`: content type values ==> Project: project, Task: task, Workflow: workflow
    * `value`: Value of global custom field, The type specified by the global custom field

    batch create :
    Sample of create multiple global custom filed:
        [
            {
              "global_custom_field_id": number,
              "value": string,
              "object_id": number,
              "content_type": string ===>can be on of these items [project,task,workflow]
            },
            {
              "global_custom_field_id": number,
              "value": string,
              "object_id": number,
              "content_type": string ===>can be on of these items [project,task,workflow]
            },
        ]

    batch update :
    Sample of update multiple global custom filed:
        [
            {
              "id": number,
              "global_custom_field_id": number,
              "value": string,
              "object_id": number,
              "content_type": string ===>can be on of these items [project,task,workflow]
            },
            {
              "id": number,
              "global_custom_field_id": number,
              "value": string,
              "object_id": number,
              "content_type": string ===>can be on of these items [project,task,workflow]
            },
        ]



    """
    queryset = GlobalCustomFieldValue.objects.none()
    model = GlobalCustomFieldValue
    serializers = {
        'default': GlobalCustomFieldValueDetailSerializer,
    }
    filterset_class = GlobalCustomFieldValueFilterSet
    filter_backends = [
        filters.DjangoFilterBackend,
    ]
    ordering_fields = []
    search_fields = []
    permission_classes_by_action = {
        'default': [IsAuthenticated, ],
        'list': [IsAuthenticated, ],
        'retrieve': [IsAuthenticated, ],
        'create': [IsAuthenticated, ],
        'update': [IsAuthenticated, ],
        'destroy': [IsAuthenticated, ],
    }

    def get_queryset(self):
        return self.model.objects.active().select_related('global_custom_field')

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        if isinstance(self.request.data, list):
            return serializer_class(many=True, *args, **kwargs)
        else:
            return serializer_class(*args, **kwargs)

    @action(methods=['delete'], detail=False)
    def multiple_delete(self, request, *args, **kwargs):
        pks = request.query_params.get('pks', None)
        if not pks:
            return Response(status=status.HTTP_404_NOT_FOUND)
        for pk in pks.split(','):
            get_object_or_404(GlobalCustomFieldValue, id=int(pk)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['put'], detail=False)
    def multiple_update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instances = []
        for item in request.data:
            instance = get_object_or_404(GlobalCustomFieldValue, id=int(item['id']))
            serializer = super().get_serializer(instance, data=item, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            instances.append(serializer.data)
        return Response(instances)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        item.is_archive = True
        item.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
