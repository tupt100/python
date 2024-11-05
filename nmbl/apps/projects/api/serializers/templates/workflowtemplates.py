from django.contrib.auth import get_user_model
from projects.models import Project, WorkflowTemplate
from rest_framework import serializers

from ..projects import ProjectBasicSerializer
from ..users import UserSerializer
from .basetemplates import BaseTemplateDetailSerializer, BaseTemplateSummarySerializer
from .templatecustomfields import TemplateCustomFieldSummarySerializer

User = get_user_model()


class WorkflowTemplatePrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super(WorkflowTemplatePrimaryKeyRelatedField, self).get_queryset()
        if not request or not queryset:
            return queryset.none()
        return queryset


class WorkflowTemplateSummarySerializer(BaseTemplateSummarySerializer):
    task_fixtures = serializers.SerializerMethodField()
    custom_fields = TemplateCustomFieldSummarySerializer(read_only=True, many=True)

    class Meta:
        model = WorkflowTemplate
        fields = BaseTemplateSummarySerializer.Meta.fields + [
            'task_fixtures',
            'custom_fields',
        ]
        read_only_fields = BaseTemplateSummarySerializer.Meta.read_only_fields + [
            'task_fixtures',
            'custom_fields',
        ]

    def get_task_fixtures(self, obj):
        from projects.api.serializers import TaskFixtureBaseSerializer

        return TaskFixtureBaseSerializer(obj.task_fixtures.all(), many=True, context=self.context).data


class WorkflowTemplateDetailSerializerSummarySerializer(
    BaseTemplateDetailSerializer, WorkflowTemplateSummarySerializer
):
    project = ProjectBasicSerializer(
        many=False,
        read_only=True,
    )
    assigned_to_users = UserSerializer(
        many=True,
        read_only=True,
    )
    assigned_to_users_id = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        allow_null=True,
        allow_empty=True,
        required=False,
        write_only=True,
        source='assigned_to_users',
    )
    project_id = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=Project.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
        source='project',
    )

    class Meta:
        model = WorkflowTemplate
        fields = (
            BaseTemplateDetailSerializer.Meta.fields
            + WorkflowTemplateSummarySerializer.Meta.fields
            + [
                'assigned_to_users',
                'assigned_to_users_id',
                'project_id',
                'project',
            ]
        )

        read_only_fields = (
            BaseTemplateDetailSerializer.Meta.read_only_fields
            + WorkflowTemplateSummarySerializer.Meta.read_only_fields
            + []
        )
