from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from projects.api.serializers import AttachmentPrimaryKeyRelatedField, TagSerializer
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    document_associate_history,
)
from projects.models import Attachment, WorkflowAbstract
from rest_framework import serializers


class WorkflowAbstractCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowAbstract
        fields = (
            'pk',
            'name',
            'owner',
            'assigned_to_users',
            'due_date',
            'importance',
            'workflow_tags',
            'attachments',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'description',
            'template_id',
            'custom_fields_value',
        )
        read_only_fields = ('pk',)
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "required": "Please Give your WorkflowAbstract a name " "in order to create it!",
                    "blank": "Please Give your WorkflowAbstract a name in " "order to create it!",
                }
            },
        }

    due_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    attachments = AttachmentPrimaryKeyRelatedField(
        queryset=Attachment.objects.active(),
        many=True,
        required=False,
        allow_null=True,
    )
    importance = serializers.IntegerField(required=True)
    workflow_tags = TagSerializer(required=False, allow_null=True)
    template_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    custom_fields_value = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't create workflow"})
        attrs['organization'] = request.user.company

        # Check whether assignee is belongs to the same organisation
        if attrs.get('owner') and attrs.get('owner').company != attrs['organization']:
            raise ValidationError({"owner": ["workflow owner not found"]})
        assigned_to_users = attrs.get('assigned_to_users', [])
        for assignee in assigned_to_users:
            if assignee.company != attrs['organization']:
                message = "Assignee doesn't belongs to your organization"
                raise ValidationError({"assigned_to_users": [message]})
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})

        from .workflows import set_variable_related_to_workflow_template

        set_variable_related_to_workflow_template(attrs)

        return attrs

    def create(self, validated_data):
        model_name = self.Meta.model._meta.model_name
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        workflow_tags = validated_data.pop('workflow_tags', [])
        instance = super(WorkflowAbstractCreateSerializer, self).create(validated_data)
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
