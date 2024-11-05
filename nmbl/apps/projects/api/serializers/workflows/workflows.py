from django.contrib.contenttypes.models import ContentType
from projects.api.serializers.workflows.abstract import WorkflowAbstractCreateSerializer
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    active_group_workload_history,
    active_tag_log_history,
    complete_group_workload_history,
    completed_tag_log_history,
    completion_workLog,
    document_associate_history,
    document_uplaod_notification_to_servicedeskuser,
    privilege_log_history,
    request_complete_notification,
    team_member_workload_history,
    update_group_work_productivity_log,
    update_group_workload_history,
    update_tag_log_history,
    update_team_member_workload_history,
    update_work_productivity_log,
    workflow_attachment_uploaded_notification,
    workflow_completed_notification,
)
from projects.models import Attachment, Workflow, WorkflowTemplate
from projects.servicedesks.models import (
    ServiceDeskExternalRequest,
    ServiceDeskRequestMessage,
)
from projects.tasks import create_workflowrank
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


def set_variable_related_to_workflow_template(attrs):
    from projects.templates.api.serializers import validate_custom_fields_value

    custom_fields_value = attrs.get('custom_fields_value')
    template_id = attrs.get('template_id')
    attrs['custom_fields_value'] = validate_custom_fields_value(
        Workflow, WorkflowTemplate, template_id, custom_fields_value
    )


class WorkflowCreateSerializer(WorkflowAbstractCreateSerializer):
    class Meta:
        model = Workflow
        fields = WorkflowAbstractCreateSerializer.Meta.fields + ('project',)
        read_only_fields = WorkflowAbstractCreateSerializer.Meta.read_only_fields
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "required": "Please Give your WorkflowAbstract a name " "in order to create it!",
                    "blank": "Please Give your WorkflowAbstract a name in " "order to create it!",
                }
            },
            "assigned_to_users": {"required": False},
        }

    def validate(self, attrs):
        # check if workflow is assigned to someone or not
        if not attrs.get('assigned_to_users') and not attrs.get('assigned_to_group'):
            raise ValidationError(
                {"detail": "please assign workflow to group or " "individual members in order to create it!."}
            )
        if attrs.get('project') and attrs.get('project').status in [2, 3]:
            raise ValidationError({"detail": "Please enter valid project"})
        return super().validate(attrs)

    def create(self, validated_data):
        instance = super(WorkflowCreateSerializer, self).create(validated_data)
        request = self.context.get('request')
        assigned_to_users = validated_data.get('assigned_to_users')
        assigned_to_group = validated_data.get('assigned_to_group')
        model_name = instance._meta.model_name
        if instance.attachments.active().exists():
            workflow_attachment_uploaded_notification(instance, instance.owner)
            if assigned_to_users:
                for workflow_user in assigned_to_users:
                    if workflow_user != instance.owner:
                        workflow_attachment_uploaded_notification(instance, workflow_user)
            if assigned_to_group:
                for workflow_group in assigned_to_group:
                    [
                        workflow_attachment_uploaded_notification(instance, group_member)
                        for group_member in workflow_group.group_members.all()
                    ]

        # transaction.on_commit(lambda: create_workflowrank(instance))
        create_workflowrank(instance)
        if instance.project:
            AuditHistoryCreate(
                f"{model_name}", instance.id, instance.last_modified_by, "Added to", instance.project.name
            )
        if instance.assigned_to_group.all().exists():
            active_group_workload_history.delay(instance, model_name)
        if instance.workflow_tags.all().exists():
            active_tag_log_history.delay(instance, model_name)
        if instance.assigned_to_users.all().exists():
            team_member_workload_history.delay(instance, model_name)
        if instance.attorney_client_privilege or instance.work_product_privilege or instance.confidential_privilege:
            privilege_log_history.delay(instance, model_name)
        if instance.description:
            ServiceDeskRequestMessage.objects.create(
                message=instance.description, workflow=instance, created_by_user=request.user, is_internal_message=True
            )
        return instance


class WorkflowUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'name',
            'owner',
            'assigned_to_users',
            'project',
            'status',
            'due_date',
            'workflow_tags',
            'importance',
            'attachments',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'is_private',
            'custom_fields_value',
            'template_id',
        )
        read_only_fields = [
            'template_id',
        ]

    due_date = serializers.DateTimeField(required=False, allow_null=True)
    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    workflow_tags = serializers.ListField(required=False, child=serializers.CharField())
    start_date = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't update workflow"})
        attrs['organization'] = request.user.company
        # Take list of attachment id and map to with DB instances
        attachments = attrs.pop('attachments', [])
        attrs['attachments'] = []
        for attach_id in attachments:
            try:
                attachment = Attachment.objects.get(id=attach_id, organization=request.user.company, is_delete=False)
            except Attachment.DoesNotExist:
                raise ValidationError({"attachments": "Attachment doesn't exist"})
            attrs['attachments'].append(attachment)
        # Check whether assignee is belongs to the same organisation
        if attrs.get('owner') and attrs.get('owner').company != attrs['organization']:
            raise ValidationError({"owner": ["workflow owner doesn't belongs " "to your organisation"]})
        status_changed = False
        if attrs.get('status') and self.instance.status != attrs.get('status'):
            status_changed = True
        attrs['status_changed'] = status_changed
        owner_changed = False
        if attrs.get('owner') and self.instance.owner != attrs.get('owner'):
            owner_changed = True
        attrs['owner_changed'] = owner_changed
        assigned_to_users = attrs.get('assigned_to_users', [])
        for assignee in assigned_to_users:
            if assignee.company != attrs['organization']:
                message = "Assignee doesn't found"
                raise ValidationError({"assigned_to_users": [message]})
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})
        if (
            status_changed
            and attrs.get('status') in [4, 5]
            and not ServiceDeskExternalRequest.objects.filter(workflow=self.instance).exists()
        ):
            raise ValidationError({"detail": "Invalid status"})
        return attrs

    def update(self, instance, validated_data):
        set_variable_related_to_workflow_template(validated_data)

        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        if 'workflow_tags' in validated_data.keys():
            tag_list = []
            workflow_tags = validated_data.pop('workflow_tags', [])
            for task_tag in workflow_tags:
                tag_list.append(GetOrCreateTags(task_tag, instance.organization))
            instance.workflow_tags.set(tag_list)
        else:
            workflow_tags = instance.workflow_tags.all()
        new_assigned_user = validated_data.get('assigned_to_users')
        new_assigned_group = validated_data.get('assigned_to_group')
        instance = super(WorkflowUpdateSerializer, self).update(instance, validated_data)
        if new_assigned_group:
            update_group_workload_history.delay(instance, "workflow")
            update_group_work_productivity_log.delay(instance, "workflow")
        if new_assigned_user:
            update_team_member_workload_history.delay(instance, "workflow")
            update_work_productivity_log.delay(instance, "workflow")
        if instance.workflow_tags.all().exists():
            update_tag_log_history.delay(instance, "workflow")
        if validated_data.get('status_changed'):
            if instance.status == 2:
                if instance.workflow_tags.all().exists():
                    completed_tag_log_history.delay(instance, "workflow")
                if instance.assigned_to_group.all().exists():
                    complete_group_workload_history.delay(instance, "workflow")
                    for workflow_group in instance.assigned_to_group.all():
                        [
                            workflow_completed_notification(instance, group_member)
                            for group_member in workflow_group.group_members.all()
                        ]
                if instance.assigned_to_users.all().exists():
                    completion_workLog.delay(instance, "workflow")
                    [
                        workflow_completed_notification(instance, workflow_user)
                        for workflow_user in instance.assigned_to_users.all()
                        if workflow_user != instance.owner
                    ]
                workflow_completed_notification(instance, instance.owner)
                request_complete_notification.delay(instance, "workflow", request.user)
        if validated_data.get('owner_changed'):
            owner_change = {"to": instance.owner, "by": request.user.id}
            AuditHistoryCreate("workflow", instance.id, owner_change, "Re-assigned to")
        # Set all attachment Generic Foreign key to `workflow`
        content_type = ContentType.objects.get(app_label='projects', model='workflow')
        attachment_exist = False
        for attachment in attachments:
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Workflow", request.user)
            attachment_exist = True
        if attachment_exist:
            AuditHistoryCreate("workflow", instance.id, request.user, "Document Uploaded at")
            if instance.status in [1, 4, 5]:
                if ServiceDeskExternalRequest.objects.filter(workflow=instance).exists():
                    document_uplaod_notification_to_servicedeskuser(instance, "workflow", request.user)
                workflow_attachment_uploaded_notification(instance, instance.owner)
                if new_assigned_user:
                    for workflow_user in new_assigned_user:
                        if workflow_user != instance.owner:
                            workflow_attachment_uploaded_notification(instance, workflow_user)
                if new_assigned_group:
                    for workflow_group in new_assigned_group:
                        [
                            workflow_attachment_uploaded_notification(instance, group_member)
                            for group_member in workflow_group.group_members.all()
                        ]
        if not workflow_tags:
            instance.workflow_tags.clear()
        return instance
