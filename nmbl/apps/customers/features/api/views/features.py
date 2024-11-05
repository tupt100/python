from rest_framework.permissions import AllowAny, DjangoModelPermissions

from nmbl.apps.base.api.views import BaseModelViewSet
from ..serializers import FeatureDetailSerializer
from ...models import Feature


class MyFeatureAPIView(BaseModelViewSet):
    """
    list:
    API to get list of feature i have
    ```
    * API To get all my features
    ```
    """
    model = Feature
    queryset = Feature.objects.active()
    serializers = {
        'default': FeatureDetailSerializer,
    }
    permission_classes_by_action = {
        'default': [DjangoModelPermissions, ],
        'list': [AllowAny, ],
        'retrieve': [DjangoModelPermissions, ],
        'create': [DjangoModelPermissions, ],
        'update': [DjangoModelPermissions, ],
        'partial_update': [DjangoModelPermissions, ],
        'destroy': [DjangoModelPermissions, ],
    }
