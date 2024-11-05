from django.contrib.auth import get_user_model
from projects.models import TaskTemplate, Workflow, WorkGroup
from projects.serializers import UserSerializer
from rest_framework import serializers

from nmbl.apps.base.api.serializers import (
    BaseModelDetailSerializer,
    BaseModelSummarySerializer,
)

from .customfields import CustomFieldSummarySerializer

User = get_user_model()


class TaskTemplateSummarySerializer(BaseModelSummarySerializer):
    created_by = UserSerializer(read_only=True)
    workflow_id = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=Workflow.objects.all(),
        allow_null=True,
        source='workflow',
    )
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=User.objects.all(),
        allow_null=True,
        source='assigned_to',
    )
    assigned_to_group = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=WorkGroup.objects.all(),
    )

    class Meta:
        model = TaskTemplate
        fields = BaseModelSummarySerializer.Meta.fields + [
            'title',
            'created_by_id',
            'task_name',
            'created_by',
            'importance',
            'workflow_id',
            'assigned_to_id',
            'assigned_to_group',
            'due_date',
            'start_date',
            'description',
            'is_private',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
            'created_by_id',
            'created_by',
        ]


class TaskTemplateDetailSerializer(BaseModelDetailSerializer, TaskTemplateSummarySerializer):
    customfield_set = CustomFieldSummarySerializer(
        read_only=True,
        many=True,
    )

    class Meta:
        model = TaskTemplate
        fields = (
            BaseModelDetailSerializer.Meta.fields
            + TaskTemplateSummarySerializer.Meta.fields
            + [
                'customfield_set',
            ]
        )

        read_only_fields = (
            BaseModelDetailSerializer.Meta.read_only_fields
            + TaskTemplateSummarySerializer.Meta.read_only_fields
            + [
                'customfield_set',
            ]
        )
