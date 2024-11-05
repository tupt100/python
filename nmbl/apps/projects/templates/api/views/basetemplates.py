from base.api.views import BaseModelViewSet
from projects.api.serializers import BaseTemplateDetailSerializer
from projects.models import BaseTemplateModel
from projects.tasksapp.api.permissions import DenyAny
from rest_framework import status
from rest_framework.response import Response

"""
ProjectTemplate
"""


class BaseTemplateViewSet(BaseModelViewSet):
    model = BaseTemplateModel

    # It's abstract view
    serializers = {
        'default': BaseTemplateDetailSerializer,
    }

    permission_classes_by_action = {
        'default': [
            DenyAny,
        ],
    }

    def perform_create(self, serializer, **kwargs):
        user = self.request.user
        kwargs['created_by_id'] = user.pk
        super(BaseTemplateViewSet, self).perform_create(serializer=serializer, **kwargs)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        item.is_delete = True
        item.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
