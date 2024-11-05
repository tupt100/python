from authentication.models import GroupAndPermission
from django.db.models import Q
from django_filters import rest_framework as filters
from projects.api.serializers import (
    TaskFixtureBaseSerializer,
    TaskFixtureCreateSerializer,
    TaskFixtureDetailSerializer,
)
from projects.helpers import user_permission_check
from projects.models import TaskFixture
from projects.servicedesks.models import ServiceDeskExternalRequest
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.viewsets import ModelViewSet


class TaskFixtureViewSet(ModelViewSet):
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
    queryset = TaskFixture.objects.all()
    serializer_class = TaskFixtureBaseSerializer

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update':
            return TaskFixtureCreateSerializer
        elif self.action == 'retrieve':
            return TaskFixtureDetailSerializer
        return TaskFixtureBaseSerializer

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'task'):
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company, created_by=user)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = TaskFixture.objects.filter(q_obj).distinct()
        else:
            queryset = TaskFixture.objects.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct()
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        task_type = self.request.query_params.get('type', None)
        if task_type:
            if task_type.lower() == "active":
                queryset = queryset.exclude(status__in=[3, 4])
            elif task_type.lower() == "archived":
                queryset = queryset.filter(status__in=[3, 4])
            else:
                queryset = TaskFixture.objects.none()
        user_ids = []
        group_ids = []
        exclude_request_task = True if self.request.query_params.get("exclude_request_task") == 'true' else False
        if exclude_request_task:
            attached_task = list(ServiceDeskExternalRequest.objects.exclude(task=None).values_list('id', flat=True))
            result_queryset = queryset.exclude(Q(id__in=attached_task) | Q(status__in=[3, 4])).distinct()
            return result_queryset
        q_user = self.request.query_params.get('user', '')
        if q_user:
            [user_ids.append(int(x)) for x in q_user.split(',')]
        q_group_member = self.request.query_params.get('group_member', '')
        q_group = self.request.query_params.get('group', '')
        if q_group:
            [group_ids.append(int(x)) for x in q_group.split(',')]
        if q_user and q_group_member and not q_group:
            result_queryset = queryset.filter(
                Q(assigned_to__id__in=user_ids) | Q(assigned_to_group__group_members__id__in=user_ids)
            ).distinct()
            return result_queryset
        elif q_user and q_group_member and q_group:
            result_queryset = queryset.filter(
                Q(assigned_to__id__in=user_ids)
                | Q(assigned_to_group__group_members__id__in=user_ids)
                | Q(assigned_to_group__id__in=group_ids)
            ).distinct()
            return result_queryset
        elif q_group and not (q_user and q_group_member):
            result_queryset = queryset.filter(Q(assigned_to_group__id__in=group_ids)).distinct()
            return result_queryset
        else:
            pass
        return queryset
