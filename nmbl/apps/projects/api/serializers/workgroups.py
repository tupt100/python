import datetime

from projects.models import Project, Task, Workflow, WorkGroup
from rest_framework import serializers

from .users import UserBasicSerializer, UserSerializer


class WorkGroupProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'name',
            'assigned_to_users',
            'assigned_to_group',
        )


class WorkGroupWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
            'assigned_to_users',
            'assigned_to_group',
        )


class WorkGroupTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'assigned_to',
            'assigned_to_group',
        )


class WorkGroupMemberCreateSerializer(serializers.Serializer):
    class Meta:
        fields = (
            'name',
            'group_members',
        )

    name = serializers.CharField(required=True)
    group_members = serializers.ListField(
        required=True,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )


class WorkGroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = (
            'id',
            'name',
            'group_members',
            'users_count',
            'project',
            'workflow',
            'task',
        )

    group_members = UserBasicSerializer(many=True)
    users_count = serializers.IntegerField()
    project = serializers.SerializerMethodField()
    workflow = serializers.SerializerMethodField()
    task = serializers.SerializerMethodField()

    def get_project(self, obj):
        return WorkGroupProjectSerializer(
            Project.objects.filter(organization=obj.organization, assigned_to_group=obj, assigned_to_users=None),
            many=True,
        ).data

    def get_workflow(self, obj):
        return WorkGroupWorkflowSerializer(
            Workflow.objects.filter(organization=obj.organization, assigned_to_group=obj, assigned_to_users=None),
            many=True,
        ).data

    def get_task(self, obj):
        return WorkGroupTaskSerializer(
            Task.objects.filter(organization=obj.organization, assigned_to_group=obj, assigned_to=None), many=True
        ).data


class UserWorkGroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = (
            'id',
            'name',
            'group_members',
            'users_count',
            'task',
        )

    group_members = UserSerializer(many=True)
    users_count = serializers.IntegerField()
    task = serializers.SerializerMethodField()

    def get_task(self, obj):
        task_queryset = self.context['task_queryset']
        task_queryset = task_queryset.filter(assigned_to_group=obj)
        date_today = datetime.datetime.utcnow().date()
        response = {
            'total_task': task_queryset.count(),
            'completed_task': task_queryset.filter(status__in=[3, 4]).count(),
            'overdue_task': task_queryset.filter(due_date__date__lt=date_today).count(),
        }
        return dict(response)


class WorkGroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = ('name',)


class WorkGroupAddMemberSerializer(serializers.Serializer):
    class Meta:
        fields = ('group_members',)

    group_members = serializers.ListField(
        required=True,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )


class WorkGroupRemoveMemberSerializer(serializers.Serializer):
    class Meta:
        fields = ('group_member',)

    group_member = serializers.IntegerField()


class CompanyWorkGroupBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = (
            'id',
            'name',
        )


class CompanyWorkGroupDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = (
            'id',
            'name',
            'group_members',
        )

    group_members = UserBasicSerializer(many=True)


class WorkGroupDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = (
            'id',
            'name',
            'group_members',
        )

    group_members = UserSerializer(many=True)
