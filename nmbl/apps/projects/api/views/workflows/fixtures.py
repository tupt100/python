from authentication.models import GroupAndPermission
from django.db.models import Q
from django_filters import rest_framework as filters
from projects.api.serializers import (
    WorkflowFixtureBaseSerializer,
    WorkflowFixtureDetailSerializer,
)
from projects.helpers import user_permission_check
from projects.models import WorkflowFixture
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.viewsets import ModelViewSet


class WorkflowFixtureViewSet(ModelViewSet):
    """
    API endpoint that allows tasks to be viewed or edited.
    """

    filter_backends = (
        filters.DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )
    search_fields = [
        'name',
    ]
    queryset = WorkflowFixture.objects.all()
    serializer_class = WorkflowFixtureBaseSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkflowFixtureBaseSerializer
        return WorkflowFixtureDetailSerializer

    def get_queryset(self):
        queryset = WorkflowFixture.objects.none()
        user = self.request.user
        company = user.company
        group = user.group
        if company:
            if user_permission_check(user, 'workflow'):
                queryset = WorkflowFixture.objects.filter(organization=company, created_by=user)
            else:
                queryset = WorkflowFixture.objects.filter(
                    Q(organization=company, created_by=user),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True,
            ).exists():
                queryset = queryset.exclude(status__in=[2, 3])
            user_ids = []
            group_ids = []
            q_user = self.request.query_params.get('user', '')
            if q_user:
                [user_ids.append(int(x)) for x in q_user.split(',')]
            q_group_member = self.request.query_params.get('group_member', '')
            q_group = self.request.query_params.get('group', '')
            if q_group:
                [group_ids.append(int(x)) for x in q_group.split(',')]
            if q_user and q_group_member and not q_group:
                result_queryset = queryset.filter(
                    Q(assigned_to_users__id__in=user_ids)
                    | Q(assigned_to_group__group_members__id__in=user_ids)
                    | Q(owner__id__in=user_ids)
                )
                return result_queryset
            elif q_user and q_group_member and q_group:
                result_queryset = queryset.filter(
                    Q(assigned_to_users__id__in=user_ids)
                    | Q(assigned_to_group__group_members__id__in=user_ids)
                    | Q(assigned_to_group__id__in=group_ids)
                    | Q(owner__id__in=user_ids)
                )
                return result_queryset
            elif q_group and not (q_user and q_group_member):
                result_queryset = queryset.filter(Q(assigned_to_group__id__in=group_ids))
                return result_queryset
            else:
                pass
        return queryset
