from django.contrib.contenttypes.models import ContentType
from projects.api.serializers import AttachmentPrimaryKeyRelatedField, TagSerializer
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    document_associate_history,
)
from projects.models import Attachment, WorkGroup
from projects.models.tasks.abstract import TaskAbstract
from projects.tasksapp.models import TaskTemplate
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404

import logging


def validate_task_custom_fields_value(model, task_template_id, data):
    task_template = None
    if task_template_id:
        task_template = get_object_or_404(TaskTemplate.objects.active(), pk=task_template_id)
    data = model.prepare_custom_fields_value_task(task_template, data)
    custom_fields_errors_list = model.clean_custom_fields_value(task_template, data, raise_error=False)
    if custom_fields_errors_list and len(custom_fields_errors_list) > 0:
        custom_fields_errors_list = {k: v.messages for d in custom_fields_errors_list for k, v in d.items()}
        raise ValidationError({'custom_fields_value': custom_fields_errors_list})
    return data


class TaskAbstractCreateSerializer(serializers.ModelSerializer):
    # serializer class for creating task.
    class Meta:
        model = TaskAbstract
        fields = (
            'pk',
            'name',
            'assigned_to',
            'attachments',
            'importance',
            'status',
            'task_tags',
            'due_date',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'prior_task',
            'after_task',
            'is_private',
            'description',
            'task_template_id',
            'custom_fields_value',
        )
        read_only_fields = ('pk',)
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "required": "Please Give your Task a " "name in order to create it!",
                    "blank": "Please Give your Task a name " "in order to create it!",
                }
            },
        }

    attachments = AttachmentPrimaryKeyRelatedField(
        queryset=Attachment.objects.active(),
        many=True,
        required=False,
        allow_null=True,
    )
    assigned_to_group = serializers.PrimaryKeyRelatedField(
        queryset=WorkGroup.objects.all(),
        many=True,
    )
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    importance = serializers.IntegerField(required=True)
    task_tags = TagSerializer(required=False, allow_null=True)
    task_template_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    custom_fields_value = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organization, " "So you can't create Task"})
        attrs['organization'] = request.user.company
        # Check whether assignee is belongs to the same organisation
        assigned_to = attrs.get('assigned_to', '')
        if assigned_to and assigned_to.company != attrs['organization']:
            raise ValidationError({"assigned_to": ["Assignee doesn't exist"]})
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})

        custom_fields_value = attrs.get('custom_fields_value', [])
        if custom_fields_value:
            task_template_id = attrs.get('task_template_id')
            attrs['custom_fields_value'] = validate_task_custom_fields_value(
                self.Meta.model, task_template_id, custom_fields_value
            )
        attrs['status'] = 1
        return attrs

    def create(self, validated_data):
        model_name = self.Meta.model._meta.model_name
        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        validated_data['created_by'] = request.user
        attachments = validated_data.pop('attachments')
        task_tags = validated_data.pop('task_tags', [])
        instance = super(TaskAbstractCreateSerializer, self).create(validated_data)
        AuditHistoryCreate(model_name, instance.id, request.user, "Created at")
        # Set all attachment Generic Foreign key to `task`
        content_type = ContentType.objects.get_for_model(instance)
        # Document Uploaded to New Task
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
        # When document is uploaded send notification
        # if attachment_exist:
        #     task_attachment_uploaded_notification(instance)
        # transaction.on_commit(lambda: create_taskrank(instance))

        return instance
