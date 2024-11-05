from django.contrib.contenttypes.models import ContentType
from projects.api.serializers.attachments import (
    DocumentBaseSerializer,
    DocumentDetailsSerializer,
)
from projects.api.serializers.servicedesks import ServiceDeskRequestBasicSerializer
from projects.api.serializers.tags import TagBasicSerializer
from projects.api.serializers.tasks.abstract import TaskAbstractCreateSerializer
from projects.api.serializers.users import UserSerializer
from projects.api.serializers.workgroups import CompanyWorkGroupBasicSerializer
from projects.helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    active_group_workload_history,
    active_tag_log_history,
    complete_dependent_task,
    complete_group_workload_history,
    completed_tag_log_history,
    completion_workLog,
    document_associate_history,
    document_uplaod_notification_to_servicedeskuser,
    email_with_site_domain,
    privilege_log_history,
    request_complete_notification,
    task_attachment_uploaded_notification,
    task_completed_notification,
    team_member_workload_history,
    update_group_work_productivity_log,
    update_group_workload_history,
    update_tag_log_history,
)
from projects.models import (
    Attachment,
    ServiceDeskExternalRequest,
    ServiceDeskRequestMessage,
    Task,
)
from projects.tasks import create_taskrank
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class TaskBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
        )


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'importance',
            'due_date',
            'status',
        )


class TaskAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'attachments',
        )

    attachments = serializers.SerializerMethodField()

    def get_attachments(self, task):
        request = self.context['request']
        return DocumentBaseSerializer(
            Attachment.objects.filter(task=task, is_delete=False), many=True, context={'request': request}
        ).data


class TaskListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'assigned_to',
            'status',
            'due_date',
            'importance',
            'created_at',
            'attachments',
            'start_date',
            'completed_percentage',
            'prior_task',
            'after_task',
            'is_private',
            'task_template_id',
        )

    assigned_to = UserSerializer()
    attachments = DocumentDetailsSerializer(source='task_attachment', many=True)


class TaskDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'assigned_to',
            'status',
            'due_date',
            'importance',
            'task_tags',
            'attachments',
            'workflow',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'is_private',
            'start_date',
            'completed_percentage',
            'servicedeskrequest_details',
            'prior_task',
            'after_task',
            'message_inbound_email',
            'task_template_id',
            'custom_fields_value',
        )

    prior_task = TaskDependencySerializer()
    after_task = TaskDependencySerializer()
    assigned_to = UserSerializer()
    attachments = DocumentDetailsSerializer(source='task_attachment', many=True)
    due_date = serializers.DateTimeField()
    task_tags = TagBasicSerializer(many=True)
    assigned_to_group = CompanyWorkGroupBasicSerializer(many=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    servicedeskrequest_details = serializers.SerializerMethodField()
    message_inbound_email = serializers.SerializerMethodField()

    def get_servicedeskrequest_details(self, task):
        return ServiceDeskRequestBasicSerializer(ServiceDeskExternalRequest.objects.filter(task=task), many=True).data

    def get_message_inbound_email(self, task):
        from django.db import connection

        return email_with_site_domain("task_{}").format(task.pk, connection.schema_name)


class TaskCreateSerializer(TaskAbstractCreateSerializer):
    class Meta:
        model = Task
        fields = TaskAbstractCreateSerializer.Meta.fields + ('workflow',)
        read_only_fields = TaskAbstractCreateSerializer.Meta.read_only_fields
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "required": "Please Give your Task a " "name in order to create it!",
                    "blank": "Please Give your Task a name " "in order to create it!",
                }
            },
            "assigned_to": {"required": False},
        }

    def validate(self, attrs):
        attrs = super(TaskCreateSerializer, self).validate(attrs)
        request = self.context.get('request')
        # check if task is assigned to someone or not
        if not attrs.get('assigned_to') and not attrs.get('assigned_to_group'):
            raise ValidationError(
                {"detail": "please assign task to group or " "individual members in order to create it!."}
            )
        if not attrs.get('workflow') and (attrs.get('prior_task') or attrs.get('after_task')):
            raise ValidationError({"detail": "Task does not have any workflow"})
        if attrs.get('workflow'):
            if attrs.get('workflow').status in [2, 3]:
                raise ValidationError({"detail": "Please enter valid workflow"})
            task_queryset = self.Meta.model.objects.all().dependency_permission(request.user)
            if (
                    attrs.get('prior_task')
                    and not task_queryset.filter(id=attrs.get('prior_task').id, workflow=attrs.get('workflow')).exists()
            ):
                raise ValidationError({"detail": "Please enter valid Prior Task"})
            if (
                    attrs.get('after_task')
                    and not task_queryset.filter(id=attrs.get('after_task').id, workflow=attrs.get('workflow')).exists()
            ):
                raise ValidationError({"detail": "Please enter valid After task"})
            if (
                    attrs.get('after_task')
                    and attrs.get('prior_task')
                    and attrs.get('after_task') == attrs.get('prior_task')
            ):
                raise ValidationError({"detail": "Prior task and after " "task should be different "})

        return attrs

    def create(self, validated_data):
        instance = super(TaskCreateSerializer, self).create(validated_data)
        model_name = instance._meta.model_name
        if instance.attachments.active().exists():
            if instance.created_by == instance.assigned_to:
                task_attachment_uploaded_notification(instance, instance.created_by)
            else:
                task_attachment_uploaded_notification(instance, instance.created_by)
                task_attachment_uploaded_notification(instance, instance.assigned_to)
            if instance.assigned_to_group.exists():
                for task_group in instance.assigned_to_group.all():
                    [
                        task_attachment_uploaded_notification(instance, group_member)
                        for group_member in task_group.group_members.all()
                    ]
        create_taskrank(instance)
        if instance.workflow:
            AuditHistoryCreate(model_name, instance.id, instance.last_modified_by, "Added to", instance.workflow.name)
        if instance.assigned_to_group.all().exists():
            active_group_workload_history.delay(instance, model_name)
        if instance.task_tags.all().exists():
            active_tag_log_history.delay(instance, model_name)
        if instance.assigned_to:
            team_member_workload_history.delay(instance, model_name)
        if instance.attorney_client_privilege or instance.work_product_privilege or instance.confidential_privilege:
            privilege_log_history.delay(instance, model_name)
        if instance.description:
            ServiceDeskRequestMessage.objects.create(
                message=instance.description,
                task=instance,
                created_by_user=instance.created_by,
                is_internal_message=True,
            )
        return instance


class TaskUpdateSerializer(serializers.ModelSerializer):
    # serializer class for updating task
    class Meta:
        model = Task
        fields = (
            'name',
            'assigned_to',
            'importance',
            'attachments',
            'task_tags',
            'workflow',
            'due_date',
            'status',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'is_private',
            'start_date',
            'completed_percentage',
            'prior_task',
            'after_task',
            'custom_fields_value',
            'task_template_id',
        )
        read_only_fields = [
            'task_template_id',
        ]

    due_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    task_tags = serializers.ListField(required=False, child=serializers.CharField())
    custom_fields_value = serializers.JSONField(
        required=False,
        default=dict,
    )

    def validate(self, attrs):
        request = self.context.get('request')

        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't create task"})
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
        if attrs.get('assigned_to') and attrs.get('assigned_to').company != attrs['organization']:
            raise ValidationError({"assigned_to": ["Task assignee doesn't exist"]})
        assignee_changed = False
        if attrs.get('assigned_to') and self.instance.assigned_to != attrs.get('assigned_to'):
            assignee_changed = True
        attrs['assignee_changed'] = assignee_changed
        status_changed = False
        if attrs.get('status') and self.instance.status != attrs.get('status'):
            status_changed = True
        attrs['status_changed'] = status_changed
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})
        if (
            status_changed
            and self.instance.prior_task
            and self.instance.prior_task.status not in [3, 4]
            and attrs.get('status') in [3, 4]
        ):
            raise ValidationError({"detail": "Prior Task is not yet completed"})
        task_reopen = False
        if status_changed:
            if self.instance.status in [3, 4] and (attrs.get('status') == 1):
                task_reopen = True
        attrs['task_reopen'] = task_reopen
        if not self.instance.workflow and (attrs.get('prior_task') or attrs.get('after_task')):
            raise ValidationError({"detail": "This task does not have any workflow"})
        task_queryset = self.Meta.model.objects.all().dependency_permission(request.user)
        if attrs.get('prior_task') and (
            not task_queryset.filter(id=attrs.get('prior_task').id, workflow=self.instance.workflow).exists()
            or attrs.get('prior_task') == self.instance
            or self.instance.status in [3, 4]
        ):
            raise ValidationError({"detail": "Please enter valid Prior Task"})
        if attrs.get('after_task') and (
            not task_queryset.filter(id=attrs.get('after_task').id, workflow=self.instance.workflow).exists()
            or attrs.get('after_task') == self.instance
            or self.instance.status in [3, 4]
        ):
            raise ValidationError({"detail": "Please enter valid After task"})
        if attrs.get('prior_task') and attrs.get('after_task') and attrs.get('after_task') == attrs.get('prior_task'):
            raise ValidationError({"detail": "Prior Task and After task must be different"})
        if attrs.get('workflow'):
            if attrs.get('prior_task') and (
                not task_queryset.filter(id=attrs.get('prior_task').id, workflow=attrs.get('workflow')).exists()
                or attrs.get('prior_task') == self.instance
                or self.instance.status in [3, 4]
            ):
                raise ValidationError({"detail": "Please enter valid Prior Task"})
            if attrs.get('after_task') and (
                not task_queryset.filter(id=attrs.get('after_task').id, workflow=attrs.get('workflow')).exists()
                or attrs.get('after_task') == self.instance
                or self.instance.status in [3, 4]
            ):
                raise ValidationError({"detail": "Please enter valid After task"})
        if (
            status_changed
            and attrs.get('status') in [5, 6]
            and not ServiceDeskExternalRequest.objects.filter(task=self.instance).exists()
        ):
            raise ValidationError({"detail": "Invalid status"})
        return attrs

    def update(self, instance, validated_data):
        from .abstract import validate_task_custom_fields_value

        custom_fields_value = validated_data.get('custom_fields_value')
        # only validate custom fields if it's being passed in
        if custom_fields_value:
            task_template_id = instance.task_template_id
            validated_data['custom_fields_value'] = validate_task_custom_fields_value(
                self.Meta.model, task_template_id, custom_fields_value
            )

        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        if 'task_tags' in validated_data.keys():
            tag_list = []
            task_tags = validated_data.pop('task_tags', [])
            for task_tag in task_tags:
                tag_list.append(GetOrCreateTags(task_tag, instance.organization))
            instance.task_tags.set(tag_list)
        else:
            task_tags = instance.task_tags.all()
        new_assigned_group = validated_data.get('assigned_to_group')
        instance = super(TaskUpdateSerializer, self).update(instance, validated_data)
        if new_assigned_group:
            update_group_workload_history.delay(instance, "task")
            update_group_work_productivity_log.delay(instance, "task")
        if instance.task_tags.all().exists():
            update_tag_log_history.delay(instance, "task")
        if validated_data.get('assignee_changed'):
            assignee_changed = {"to": instance.assigned_to, "by": request.user.id}
            AuditHistoryCreate("task", instance.id, assignee_changed, "Re-assigned to")
        if validated_data.get('status_changed'):
            if instance.status in [4, 3]:
                if Task.objects.filter(prior_task=instance).exists():
                    complete_dependent_task(instance, instance.last_modified_by)
                if instance.status == 3:
                    if instance.task_tags.all().exists():
                        completed_tag_log_history.delay(instance, "task")
                    if instance.assigned_to_group.all().exists():
                        complete_group_workload_history.delay(instance, "task")
                        for task_group in instance.assigned_to_group.all():
                            [
                                task_completed_notification(instance, group_member)
                                for group_member in task_group.group_members.all()
                            ]
                    if instance.assigned_to:
                        completion_workLog.delay(instance, "task")
                    task_completed_notification(instance, instance.created_by)
                    task_completed_notification(instance, instance.assigned_to)
                    request_complete_notification.delay(instance, "task", request.user)
        if validated_data.get('task_reopen'):
            if instance.task_tags.all().exists():
                active_tag_log_history.delay(instance, "task")
        # Set all attachment Generic Foreign key to `project`
        content_type = ContentType.objects.get(app_label='projects', model='task')
        attachment_exist = False
        for attachment in attachments:
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Task", request.user)
            attachment_exist = True
        if attachment_exist:
            AuditHistoryCreate("task", instance.id, request.user, "Document Uploaded at")
            if instance.status not in [3, 4]:
                if ServiceDeskExternalRequest.objects.filter(task=instance).exists():
                    document_uplaod_notification_to_servicedeskuser(instance, "task", request.user)
                if instance.created_by == instance.assigned_to:
                    task_attachment_uploaded_notification(instance, instance.created_by)
                else:
                    task_attachment_uploaded_notification(instance, instance.created_by)
                    task_attachment_uploaded_notification(instance, instance.assigned_to)
                if new_assigned_group:
                    for task_group in new_assigned_group:
                        [
                            task_attachment_uploaded_notification(instance, group_member)
                            for group_member in task_group.group_members.all()
                        ]
        if not task_tags:
            instance.task_tags.clear()
        return instance
