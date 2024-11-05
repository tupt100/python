from django.contrib.contenttypes.models import ContentType
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    document_associate_history,
)
from projects.models import TaskFixture, WorkflowFixture
from projects.templates.models import WorkflowTemplate
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..templates import (
    WorkflowTemplatePrimaryKeyRelatedField,
    WorkflowTemplateSummarySerializer,
)
from ..workflows import WorkflowFixtureBaseSerializer
from .abstract import TaskAbstractCreateSerializer


class TaskFixtureCreateSerializer(TaskAbstractCreateSerializer):
    class Meta:
        model = TaskFixture
        fields = TaskAbstractCreateSerializer.Meta.fields + (
            'workflow_template_id',
            'workflow_template',
            'workflow_fixture_id',
            'workflow_fixture',
        )
        read_only_fields = TaskAbstractCreateSerializer.Meta.read_only_fields

    workflow_template_id = WorkflowTemplatePrimaryKeyRelatedField(
        source='workflow_template',
        queryset=WorkflowTemplate.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    workflow_template = WorkflowTemplateSummarySerializer(
        read_only=True,
    )

    workflow_fixture_id = serializers.PrimaryKeyRelatedField(
        source='workflow_fixture',
        queryset=WorkflowFixture.objects.all(),
        required=False,
        allow_null=True,
        allow_empty=True,
        write_only=True,
    )
    workflow_fixture = WorkflowFixtureBaseSerializer(
        read_only=True,
    )
    due_date = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        task_queryset = self.Meta.model.objects.all().dependency_permission(request.user)
        if (
            attrs.get('prior_task')
            and not task_queryset.filter(
                id=attrs.get('prior_task').id, workflow_template=attrs.get('workflow_template').pk
            ).exists()
        ):
            raise ValidationError({"detail": "Please enter valid Prior Task"})
        if (
            attrs.get('after_task')
            and not task_queryset.filter(
                id=attrs.get('after_task').id, workflow_template=attrs.get('workflow_template').pk
            ).exists()
        ):
            raise ValidationError({"detail": "Please enter valid After task"})
        if attrs.get('after_task') and attrs.get('prior_task') and attrs.get('after_task') == attrs.get('prior_task'):
            raise ValidationError({"detail": "Prior task and after " "task should be different "})

        return attrs

    def update(self, instance, validated_data):
        model_name = self.Meta.model._meta.model_name
        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        task_tags = validated_data.pop('task_tags', [])
        instance = super(TaskFixtureCreateSerializer, self).update(instance, validated_data)
        content_type = ContentType.objects.get_for_model(instance)
        attachment_exist = False
        for attachment in attachments:
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history(
                "attachment", attachment.id, instance.name, f"Associated {model_name}", request.user
            )
            attachment_exist = True
        if attachment_exist:
            AuditHistoryCreate(model_name, instance.id, request.user, "Document Uploaded at")
        tag_list = []
        for task_tag in task_tags:
            tag_list.append(GetOrCreateTags(task_tag, instance.organization))
        instance.task_tags.set(tag_list)
        return instance


class TaskFixtureBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskFixture
        fields = (
            'pk',
            'name',
            'workflow_template_id',
            'workflow_fixture_id',
        )
        read_only_fields = (
            'pk',
            'name',
            'workflow_template_id',
            'workflow_fixture_id',
        )


class TaskFixtureDetailSerializer(TaskFixtureCreateSerializer):
    class Meta:
        model = TaskFixture
        fields = TaskFixtureCreateSerializer.Meta.fields
        read_only_fields = TaskFixtureCreateSerializer.Meta.read_only_fields
