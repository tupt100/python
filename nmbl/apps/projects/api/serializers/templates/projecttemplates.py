from django.contrib.auth import get_user_model
from projects.models import ProjectTemplate
from rest_framework import serializers

from ..users import UserSerializer
from .basetemplates import BaseTemplateDetailSerializer, BaseTemplateSummarySerializer
from .templatecustomfields import TemplateCustomFieldSummarySerializer

User = get_user_model()


class ProjectTemplatePrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super(ProjectTemplatePrimaryKeyRelatedField, self).get_queryset()
        if not request or not queryset:
            return queryset.none()
        return queryset


class ProjectTemplateSummarySerializer(BaseTemplateSummarySerializer):
    workflow_fixtures = serializers.SerializerMethodField()
    custom_fields = TemplateCustomFieldSummarySerializer(read_only=True, many=True)

    class Meta:
        model = ProjectTemplate
        fields = BaseTemplateSummarySerializer.Meta.fields + [
            'workflow_fixtures',
            'custom_fields',
        ]
        read_only_fields = BaseTemplateSummarySerializer.Meta.read_only_fields + [
            'custom_fields',
        ]

    def get_workflow_fixtures(self, obj):
        from projects.api.serializers import WorkflowFixtureBaseSerializer

        return WorkflowFixtureBaseSerializer(obj.workflow_fixtures.all(), many=True, context=self.context).data


class ProjectTemplateDetailSerializerSummarySerializer(BaseTemplateDetailSerializer, ProjectTemplateSummarySerializer):
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

    class Meta:
        model = ProjectTemplate
        fields = (
            BaseTemplateDetailSerializer.Meta.fields
            + ProjectTemplateSummarySerializer.Meta.fields
            + [
                'assigned_to_users',
                'assigned_to_users_id',
            ]
        )

        read_only_fields = (
            BaseTemplateDetailSerializer.Meta.read_only_fields
            + ProjectTemplateSummarySerializer.Meta.read_only_fields
            + []
        )
