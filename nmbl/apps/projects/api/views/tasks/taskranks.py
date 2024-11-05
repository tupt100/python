from projects.models import Task, TaskRank
from projects.permissions import RankPermission
from projects.serializers import TaskRankSerializer
from rest_framework.viewsets import ModelViewSet


class TaskRankViewSet(ModelViewSet):
    model = Task
    permission_classes = (RankPermission,)

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = (
            TaskRank.objects.filter(task__organization=company, user=user)
            .exclude(task__status__in=[3, 4])
            .order_by('-rank')
        )
        return queryset

    def get_serializer_class(self):
        if self.request.method in ['PATCH']:
            return TaskRankSerializer
        return None
