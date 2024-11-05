import datetime

from authentication.models import GroupAndPermission
from django.db.models import Q
from projects.helpers import user_permission_check
from projects.models import Task
from projects.permissions import UserWorkGroupPermission
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet


class TaskStatisticsViewSet(ListModelMixin, GenericViewSet):
    """
    list:
    * API to get type wise importance of task which is assigned to user
    ```
    > API will return following detail
    * total number of task and completed task
    * total number of task which are passed due date today
    * importance of task which are assigned to me
    * total number of task which are passed due date but still active
    ```
    """

    permission_classes = (
        IsAuthenticated,
        UserWorkGroupPermission,
    )

    def get_queryset(self):
        user = self.request.user
        group = user.group
        company = user.company
        queryset = Task.objects.none()
        if user_permission_check(user, 'task'):
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = Task.objects.filter(q_obj).distinct('id')
        else:
            queryset = Task.objects.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        return queryset

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        active_task_objs = queryset.exclude(status__in=[3, 4])
        total_task = queryset.count()
        completed = queryset.filter(status__in=[3, 4]).count()
        date_today = datetime.datetime.utcnow().date()
        today_due = active_task_objs.filter(due_date__date=date_today).count()
        total_due = active_task_objs.filter(due_date__date__lt=date_today).count()
        response = {
            'high': active_task_objs.filter(importance=3).count(),
            'med': active_task_objs.filter(importance=2).count(),
            'low': active_task_objs.filter(importance=1).count(),
            'completed': completed,
            'total_task': total_task,
            'due_today': today_due,
            'total_due': total_due,
        }
        return Response(dict(response))
