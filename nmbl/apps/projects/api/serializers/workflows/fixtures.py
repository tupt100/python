from django.contrib.contenttypes.models import ContentType
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    document_associate_history,
)
from projects.models import ProjectTemplate, WorkflowFixture
from rest_framework import serializers

from ..templates import (
    ProjectTemplatePrimaryKeyRelatedField,
    ProjectTemplateSummarySerializer,
)
from .abstract import WorkflowAbstractCreateSerializer


class WorkflowFixtureBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowFixture
        fields = (
            'pk',
            'name',
            'project_template_id',
        )
        read_only_fields = (
            'pk',
            'name',
            'project_template_id',
        )


class WorkflowFixtureDetailSerializer(WorkflowAbstractCreateSerializer):
    due_date = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = WorkflowFixture
        fields = WorkflowAbstractCreateSerializer.Meta.fields + (
            'project_template_id',
            'project_template',
        )
        read_only_fields = WorkflowAbstractCreateSerializer.Meta.read_only_fields

    project_template_id = ProjectTemplatePrimaryKeyRelatedField(
        source='project_template',
        queryset=ProjectTemplate.objects.all(),
        required=True,
        write_only=True,
    )
    project_template = ProjectTemplateSummarySerializer(
        read_only=True,
    )

    def update(self, instance, validated_data):
        model_name = self.Meta.model._meta.model_name
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        workflow_tags = validated_data.pop('workflow_tags', [])
        instance = super(WorkflowFixtureDetailSerializer, self).update(instance, validated_data)
        content_type = ContentType.objects.get_for_model(instance)
        AuditHistoryCreate(model_name, instance.id, request.user, "Created at")
        # Set all attachment Generic Foreign key to `WorkflowAbstract`
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
        for workflow_tag in workflow_tags:
            tag_list.append(GetOrCreateTags(workflow_tag, instance.organization))
        instance.workflow_tags.set(tag_list)
        return instance
