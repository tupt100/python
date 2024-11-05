import abc
from abc import abstractmethod

import six
from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from nmbl.apps.base.api.serializers import BaseModelDetailSerializer

"""
Base Model
"""


@six.add_metaclass(abc.ABCMeta)
class BaseModelViewSet(ModelViewSet):
    serializers = {
        'default': BaseModelDetailSerializer,
    }
    permission_classes_by_action = {
    }

    @property
    @abstractmethod
    def model(self):
        raise NotImplementedError

    @classmethod
    def get_permission_classes_by_action(cls):
        permissions = {
            'default': [IsAdminUser, ],
            'list': [IsAdminUser, ],
            'retrieve': [IsAdminUser, ],
            'create': [IsAdminUser, ],
            'update': [IsAdminUser, ],
            'partial_update': [IsAdminUser, ],
            'destroy': [IsAdminUser, ],
        }

        permissions.update(cls.permission_classes_by_action)
        return permissions

    def get_serializer_class(self):
        serializer_class = self.serializers.get(self.action, self.serializers['default'])
        return serializer_class

    def get_permissions(self):
        permissions = self.get_permission_classes_by_action()
        act = self.action
        result = [
            permission() for permission in permissions.get(
                act, permissions['default']
            )
        ]
        return result

    def perform_create(self, serializer, *args, **kwargs):
        serializer.save(**kwargs)

    def get_queryset(self):
        return self.model.objects.active()

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        try:
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError as e:
            error = []
            for item in e.protected_objects.all():
                error.append(
                    _('Deleting this item depends on the %(verbose_name)s with ID %(id)s. (%(title)s)') % {
                        'verbose_name': item._meta.verbose_name,
                        'id': str(item.pk),
                        'title': str(item),
                    }
                )
            return Response({'non_field_errors': error}, status=status.HTTP_400_BAD_REQUEST)
