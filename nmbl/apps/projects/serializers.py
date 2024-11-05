import datetime

from authentication.models import Organization, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Max, Min
from django.utils.crypto import get_random_string
from projects.api.serializers import (
    AttachmentSerializer,
    CompanyWorkGroupBasicSerializer,
    DocumentBaseSerializer,
    DocumentDetailsSerializer,
    ProjectBasicSerializer,
    RequestTaskListSerializer,
    ServiceDeskRequestBasicSerializer,
    ServiceDeskRequestSerializer,
    ServiceDeskUserBasicSerializer,
    TagBasicSerializer,
    TaskAttachmentSerializer,
    TaskBasicSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
    UserBasicSerializer,
    UserSerializer,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from nmbl.apps.base.constants import DATE_FORMAT_OUT

from .helpers import (
    AuditHistoryCreate,
    GetOrCreateTags,
    active_group_workload_history,
    active_tag_log_history,
    complete_group_workload_history,
    completed_tag_log_history,
    completion_workLog,
    document_associate_history,
    document_uplaod_notification_to_servicedeskuser,
    email_with_site_domain,
    privilege_log_history,
    project_attachment_uploaded_notification,
    project_completed_notification,
    request_complete_notification,
    team_member_workload_history,
    update_group_work_productivity_log,
    update_group_workload_history,
    update_tag_log_history,
    update_team_member_workload_history,
    update_work_productivity_log,
)
from .models import (
    Attachment,
    AuditHistory,
    CompletionLog,
    GroupWorkLoadLog,
    Privilage_Change_Log,
    Project,
    ProjectRank,
    ProjectTemplate,
    Request,
    ServiceDeskAttachment,
    ServiceDeskExternalCCUser,
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskRequestMessage,
    ServiceDeskUserInformation,
    Tag,
    TagChangeLog,
    Task,
    TaskRank,
    TeamMemberWorkLoadLog,
    Workflow,
    WorkflowRank,
    WorkProductivityLog,
)
from .tasks import create_projectrank, rerankProject, rerankTask, rerankWorkflow

options = {'size': (170, 170), 'crop': True}


# ############ Base Serializers START ############


class WorkflowBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
            'importance',
        )


class WorkflowBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
        )


# ############ Base Serializers END ############

# ############ Tag Serializers START ###########


class TagCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('tag',)

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organization, " "So you can't create Project"})
        attrs['organization'] = request.user.company
        return attrs

    def create(self, validated_data):
        tag, created = Tag.objects.get_or_create(
            tag=validated_data['tag'].upper(), organization=validated_data['organization']
        )
        if not created:
            raise ValidationError({"detail": "Tag with the same name is already exist"})
        return tag

    def to_representation(self, instance):
        return {'id': instance.id, 'tag': instance.tag}


class TagDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            'id',
            'tag',
            'attached_to',
        )

    attached_to = serializers.SerializerMethodField()

    def get_attached_to(self, obj):
        data = {
            'project': ProjectBasicSerializer(
                Project.objects.filter(project_tags=obj.id, status__in=[1, 4, 5], organization=obj.organization),
                many=True,
            ).data,
            'workflow': WorkflowBaseSerializer(
                Workflow.objects.filter(workflow_tags=obj.id, status__in=[1, 4, 5], organization=obj.organization),
                many=True,
            ).data,
            'task': TaskBasicSerializer(
                Task.objects.filter(task_tags=obj.id, organization=obj.organization).exclude(status__in=[3, 4]),
                many=True,
            ).data,
            'attachment': AttachmentSerializer(
                Attachment.objects.filter(document_tags=obj.id, organization=obj.organization), many=True
            ).data,
        }
        return data


class TagCountDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            'id',
            'tag',
            'attached_to',
        )

    attached_to = serializers.SerializerMethodField()

    def get_attached_to(self, obj):
        data = {
            'project': ProjectBasicSerializer(
                Project.objects.filter(project_tags=obj.id, organization=obj.organization), many=True
            ).data,
            'workflow': WorkflowBaseSerializer(
                Workflow.objects.filter(workflow_tags=obj.id, organization=obj.organization), many=True
            ).data,
            'task': TaskBasicSerializer(
                Task.objects.filter(task_tags=obj.id, organization=obj.organization), many=True
            ).data,
            'attachment': AttachmentSerializer(
                Attachment.objects.filter(document_tags=obj.id, organization=obj.organization), many=True
            ).data,
            'counts': [],
        }
        tag_count = {
            'project_count': len(data['project']),
            'workflow_count': len(data['workflow']),
            'task_count': len(data['task']),
            'attachment_count': len(data['attachment']),
        }
        data['counts'].append(tag_count)
        return data


# ############ Tag Serializers END ###########


# ############ WorkGroup Serializers START ############


# ############ WorkGroup Serializers END ############

# ############ Project Serializers START ############


class WorkflowAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
            'attachments',
            'task',
            'due_date',
        )

    attachments = serializers.SerializerMethodField()
    task = serializers.SerializerMethodField()

    def get_attachments(self, workflow):
        request = self.context['request']
        return DocumentBaseSerializer(
            Attachment.objects.filter(workflow=workflow, is_delete=False), many=True, context={'request': request}
        ).data

    def get_task(self, workflow_obj):
        if workflow_obj.task_workflow.all().exists():
            request = self.context.get('request')
            return TaskAttachmentSerializer(
                Task.objects.filter(workflow=workflow_obj), many=True, context={'request': request}
            ).data
        return None


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'name',
            'owner',
            'assigned_to_users',
            'importance',
            'project_tags',
            'attachments',
            'due_date',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'description',
            'template_id',
            'custom_fields_value',
        )
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "required": "Please Give your Project a " "name in order to create it!",
                    "blank": "Please Give your Project a name " "in order to create it!",
                }
            },
            "owner": {"required": False},
            "assigned_to_users": {"required": False},
        }

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    importance = serializers.IntegerField(required=True)
    project_tags = serializers.ListField(required=False, child=serializers.CharField())
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    template_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    custom_fields_value = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't create Project"})
        attrs['organization'] = request.user.company
        if not attrs.get('assigned_to_users') and not attrs.get('assigned_to_group'):
            raise ValidationError(
                {"detail": "please assign project to group or " "individual members in order to create it!."}
            )
        # Take list of attachment id and map to with DB instances
        attachments = attrs.pop('attachments', [])
        attrs['attachments'] = []
        for attach_id in attachments:
            try:
                attachment = Attachment.objects.get(id=attach_id, organization=request.user.company, is_delete=False)
            except Attachment.DoesNotExist:
                raise ValidationError({"attachments": "Attachment doesn't exist"})
            attrs['attachments'].append(attachment)
        # Check whether assignee is belongs to the same organization
        if attrs.get('owner') and attrs.get('owner').company != attrs['organization']:
            raise ValidationError({"owner": ["Project owner doesn't " "belongs to your organization"]})
        assigned_to_users = attrs.get('assigned_to_users', [])
        for assignee in assigned_to_users:
            if assignee.company != attrs['organization']:
                message = "Assignee {} doesn't belongs " "to your organisation".format(assignee.id)
                raise ValidationError({"assigned_to_users": [message]})
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})

        set_variable_related_to_project_template(attrs)

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        validated_data['created_by'] = request.user
        validated_data['assigned_by'] = request.user
        attachments = validated_data.pop('attachments')
        project_tags = validated_data.pop('project_tags', [])
        assigned_to_users = validated_data.get('assigned_to_users')
        assigned_to_group = validated_data.get('assigned_to_group')
        instance = super(ProjectCreateSerializer, self).create(validated_data)
        AuditHistoryCreate("project", instance.id, request.user, "Created at")
        # Set all attachment Generic Foreign key to `project`
        content_type = ContentType.objects.get(app_label='projects', model='project')
        attachment_exist = False
        for attachment in attachments:
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Project", request.user)
            attachment_exist = True
        if attachment_exist:
            project_attachment_uploaded_notification(instance, instance.owner)
            if assigned_to_users:
                for project_user in assigned_to_users:
                    if project_user != instance.owner:
                        project_attachment_uploaded_notification(instance, project_user)
            if assigned_to_group:
                for projects_group in assigned_to_group:
                    [
                        project_attachment_uploaded_notification(instance, group_member)
                        for group_member in projects_group.group_members.all()
                    ]
            AuditHistoryCreate("project", instance.id, request.user, "Document Uploaded at")
        tag_list = []
        for project_tag in project_tags:
            tag_list.append(GetOrCreateTags(project_tag, instance.organization))
        instance.project_tags.set(tag_list)
        if instance.project_tags.all().exists():
            active_tag_log_history.delay(instance, "project")
        # transaction.on_commit(lambda: create_projectrank(instance))
        create_projectrank(instance)
        if instance.assigned_to_group.all().exists():
            active_group_workload_history.delay(instance, "project")
        if instance.assigned_to_users.all().exists():
            team_member_workload_history.delay(instance, "project")
        if instance.attorney_client_privilege or instance.work_product_privilege or instance.confidential_privilege:
            privilege_log_history.delay(instance, "project")
        if instance.description:
            ServiceDeskRequestMessage.objects.create(
                message=instance.description, project=instance, created_by_user=request.user, is_internal_message=True
            )
        return instance


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'name',
            'importance',
            'attachments',
            'project_tags',
            'owner',
            'assigned_to_users',
            'status',
            'due_date',
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

    due_date = serializers.DateTimeField(required=False)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    project_tags = serializers.ListField(required=False, child=serializers.CharField())

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't update Project"})
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
            raise ValidationError({"owner": ["Project owner doesn't " "belongs to your organization"]})
        assigned_to_users = attrs.get('assigned_to_users', [])
        for assignee in assigned_to_users:
            if assignee.company != attrs['organization']:
                message = "Assignee doesn't exist"
                raise ValidationError({"assigned_to_users": [message]})
        status_changed = False
        if attrs.get('status') and self.instance.status != attrs.get('status'):
            status_changed = True
        attrs['status_changed'] = status_changed
        owner_changed = False
        if attrs.get('owner') and self.instance.owner != attrs.get('owner'):
            owner_changed = True
        attrs['owner_changed'] = owner_changed
        assigned_to_group = attrs.get('assigned_to_group', [])
        for group in assigned_to_group:
            if group.organization != attrs['organization']:
                raise ValidationError({"assigned_to_group": "Group not found "})
        if (
            status_changed
            and attrs.get('status') in [4, 5]
            and not ServiceDeskExternalRequest.objects.filter(project=self.instance).exists()
        ):
            raise ValidationError({"detail": "Invalid status"})
        return attrs

    def update(self, instance, validated_data):
        set_variable_related_to_project_template(validated_data)

        request = self.context.get('request')
        validated_data['last_modified_by'] = request.user
        attachments = validated_data.pop('attachments')
        if 'project_tags' in validated_data.keys():
            tag_list = []
            project_tags = validated_data.pop('project_tags', [])
            for project_tag in project_tags:
                tag_list.append(GetOrCreateTags(project_tag, instance.organization))
            instance.project_tags.set(tag_list)
        else:
            project_tags = instance.project_tags.all()
        new_assigned_user = validated_data.get('assigned_to_users')
        new_assigned_group = validated_data.get('assigned_to_group')
        instance = super(ProjectUpdateSerializer, self).update(instance, validated_data)
        if new_assigned_group:
            update_group_workload_history.delay(instance, "project")
            update_group_work_productivity_log.delay(instance, "project")
        if new_assigned_user:
            update_team_member_workload_history.delay(instance, "project")
            update_work_productivity_log.delay(instance, "project")
        if instance.project_tags.all().exists():
            update_tag_log_history.delay(instance, "project")
        if validated_data.get('status_changed'):
            if instance.status == 2:
                if instance.project_tags.all().exists():
                    completed_tag_log_history.delay(instance, "project")
                if instance.assigned_to_group.all().exists():
                    complete_group_workload_history.delay(instance, "project")
                    for projects_group in instance.assigned_to_group.all():
                        [
                            project_completed_notification(instance, group_member)
                            for group_member in projects_group.group_members.all()
                        ]
                if instance.assigned_to_users.all().exists():
                    completion_workLog.delay(instance, "project")
                    [
                        project_completed_notification(instance, project_user)
                        for project_user in instance.assigned_to_users.all()
                        if project_user != instance.owner
                    ]
                project_completed_notification(instance, instance.owner)
                request_complete_notification.delay(instance, "project", request.user)
        if validated_data.get('owner_changed'):
            owner_change = {"to": instance.owner, "by": request.user.id}
            AuditHistoryCreate("project", instance.id, owner_change, "Re-assigned to")
        #  if instance.owner not in [instance.assigned_to_users,
        #  request.user]:
        #  project_assigned_notification(instance,
        #  instance.owner)

        # Set all attachment Generic Foreign key to `project`
        content_type = ContentType.objects.get(app_label='projects', model='project')
        attachment_exist = False
        for attachment in attachments:
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Project", request.user)
            attachment_exist = True
        if attachment_exist:
            AuditHistoryCreate("project", instance.id, request.user, "Document Uploaded at")
            if instance.status in [1, 4, 5]:
                if ServiceDeskExternalRequest.objects.filter(project=instance).exists():
                    document_uplaod_notification_to_servicedeskuser(instance, "project", request.user)
                project_attachment_uploaded_notification(instance, instance.owner)
                if new_assigned_user:
                    for project_user in new_assigned_user:
                        if project_user != instance.owner:
                            project_attachment_uploaded_notification(instance, project_user)
                if new_assigned_group:
                    for projects_group in new_assigned_group:
                        [
                            project_attachment_uploaded_notification(instance, group_member)
                            for group_member in projects_group.group_members.all()
                        ]
        if not project_tags:
            instance.project_tags.clear()
        return instance


class ProjectStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ('owner',)


class ProjectRankSwapSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    from_rank = serializers.IntegerField()
    to_rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        from_rank_id = attrs.get('from_rank')
        to_rank_id = attrs.get('to_rank')
        if not ProjectRank.objects.filter(user=request.user, rank=from_rank_id).count():
            raise ValidationError({"from_rank": ["Invalid from rank id"]})
        if not ProjectRank.objects.filter(user=request.user, rank=to_rank_id).count():
            raise ValidationError({"to_rank": ["Invalid to rank id"]})
        return attrs


class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'name',
            'owner',
            'assigned_to_users',
            'importance',
            'due_date',
            'task',
            'workflow',
            'attachments',
            'template_id',
        )

    owner = UserBasicSerializer()
    assigned_to_users = UserSerializer(many=True)
    attachments = serializers.SerializerMethodField()
    task = serializers.SerializerMethodField()
    workflow = serializers.SerializerMethodField()

    def get_task(self, project_obj):
        if 'project_task_data' in self.context:
            return self.context['project_task_data']
        if project_obj.workflow_assigned_project.all().exists():
            date_today = datetime.datetime.utcnow().date()
            workflow = project_obj.workflow_assigned_project.all().values_list('id', flat=True)[::1]
            tasks = Task.objects.filter(workflow_id__in=workflow)
            data = {
                'total_task': tasks.count(),
                'completed_task': tasks.filter(status__in=[3, 4]).count(),
                'passed_due': tasks.filter(due_date__date__lt=date_today).exclude(status__in=[3, 4]).count(),
            }
            return data
        return None

    def get_attachments(self, project_obj):
        request = self.context['request']
        return DocumentBaseSerializer(
            Attachment.objects.filter(project=project_obj, is_delete=False), many=True, context={'request': request}
        ).data

    def get_workflow(self, project_obj):
        if project_obj.workflow_assigned_project.all().exists():
            request = self.context.get('request')
            return WorkflowAttachmentSerializer(
                project_obj.workflow_assigned_project.all(), many=True, context={'request': request}
            ).data
        return None


class ProjectRankListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRank
        fields = (
            'project',
            'rank',
            'id',
        )

    project = serializers.SerializerMethodField()

    def get_project(self, project_rank):
        request = self.context.get('request')
        return ProjectListSerializer(
            project_rank.project,
            context={
                'request': request,
                'project_task_data': {
                    'total_task': project_rank.total_task,
                    'completed_task': project_rank.completed_task,
                    'passed_due': project_rank.passed_due,
                },
            },
        ).data


class ProjectDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'owner',
            'name',
            'assigned_to_users',
            'importance',
            'project_tags',
            'status',
            'due_date',
            'attachments',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'is_private',
            'message_inbound_email',
            'template_id',
            'custom_fields_value',
        )

    owner = UserSerializer()
    attachments = serializers.SerializerMethodField()
    assigned_to_users = UserSerializer(many=True)
    due_date = serializers.DateTimeField()
    project_tags = TagBasicSerializer(many=True)
    assigned_to_group = CompanyWorkGroupBasicSerializer(many=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    message_inbound_email = serializers.SerializerMethodField()

    def get_attachments(self, project):
        request = self.context['request']
        return DocumentDetailsSerializer(
            Attachment.objects.filter(project=project, is_delete=False), many=True, context={'request': request}
        ).data

    def get_message_inbound_email(self, project):
        from django.db import connection

        return email_with_site_domain("project_{}").format(project.pk, connection.schema_name)


class ProjectRankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRank
        fields = ('project', 'rank', 'id')

    project = serializers.SerializerMethodField()

    def get_project(self, project_rank):
        request = self.context.get('request')
        return ProjectDetailSerializer(project_rank.project, context={'request': request}).data


# ############ Project Serializers END ############

# ############ Workflow Serializers START ############


def set_variable_related_to_project_template(attrs):
    from projects.templates.api.serializers import validate_custom_fields_value

    custom_fields_value = attrs.get('custom_fields_value')
    template_id = attrs.get('template_id')
    attrs['custom_fields_value'] = validate_custom_fields_value(
        Project, ProjectTemplate, template_id, custom_fields_value
    )


class WorkflowRankSwapSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    from_rank = serializers.IntegerField()
    to_rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        from_rank_id = attrs.get('from_rank')
        to_rank_id = attrs.get('to_rank')
        WorkflowRank.objects.filter(user=request.user, rank__range=sorted([from_rank_id, to_rank_id]))
        if not WorkflowRank.objects.filter(user=request.user, rank=from_rank_id).count():
            raise ValidationError({"from_rank": ["Invalid from rank id"]})
        if not WorkflowRank.objects.filter(user=request.user, rank=to_rank_id).count():
            raise ValidationError({"to_rank": ["Invalid to rank id"]})
        return attrs


class WorkflowListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
            'importance',
            'owner',
            'due_date',
            'total_task',
            'completed_task',
            'task',
            'template_id',
        )

    owner = UserSerializer()
    due_date = serializers.DateTimeField()
    total_task = serializers.SerializerMethodField()
    completed_task = serializers.SerializerMethodField()
    task = serializers.SerializerMethodField()

    def get_total_task(self, workflow_obj):
        return Task.objects.filter(workflow=workflow_obj).count()

    def get_completed_task(self, workflow_obj):
        return Task.objects.filter(workflow=workflow_obj, status__in=[3, 4]).count()

    def get_task(self, workflow_obj):
        request = self.context.get('request')
        return TaskAttachmentSerializer(
            Task.objects.filter(workflow=workflow_obj), many=True, context={'request': request}
        ).data


class WorkflowRankListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRank
        fields = ('workflow', 'rank', 'id')

    workflow = serializers.SerializerMethodField()

    def get_workflow(self, workflow_rank):
        request = self.context.get('request')
        return WorkflowListSerializer(workflow_rank.workflow, context={'request': request}).data


class WorkflowDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'importance',
            'project',
            'name',
            'owner',
            'due_date',
            'assigned_to_users',
            'status',
            'workflow_tags',
            'attachments',
            'attorney_client_privilege',
            'work_product_privilege',
            'confidential_privilege',
            'assigned_to_group',
            'start_date',
            'is_private',
            'servicedeskrequest_details',
            'message_inbound_email',
            'template_id',
            'custom_fields_value',
        )

    owner = UserSerializer()
    due_date = serializers.DateTimeField()
    attachments = serializers.SerializerMethodField()
    assigned_to_users = UserSerializer(many=True)
    workflow_tags = TagBasicSerializer(many=True)
    assigned_to_group = CompanyWorkGroupBasicSerializer(many=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    servicedeskrequest_details = serializers.SerializerMethodField()
    message_inbound_email = serializers.SerializerMethodField()

    def get_attachments(self, workflow):
        request = self.context['request']
        return DocumentDetailsSerializer(
            Attachment.objects.filter(workflow=workflow, is_delete=False), many=True, context={'request': request}
        ).data

    def get_servicedeskrequest_details(self, workflow):
        return ServiceDeskRequestBasicSerializer(
            ServiceDeskExternalRequest.objects.filter(workflow=workflow).first()
        ).data

    def get_message_inbound_email(self, workflow):
        from django.db import connection

        return email_with_site_domain("workflow_{}").format(workflow.pk, connection.schema_name)


class WorkflowRankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRank
        fields = ('workflow', 'rank', 'id')

    workflow = serializers.SerializerMethodField()

    def get_workflow(self, workflow_rank):
        request = self.context.get('request')
        return WorkflowDetailSerializer(workflow_rank.workflow, context={'request': request}).data


# ############ Workflow Serializers END ############

# ############ Task Serializers START ############
class ItemTitleRenameSerializer(serializers.Serializer):
    """
    Serializer class to validate title of a
    item(Project/WF/Task) to update.
    """

    name = serializers.CharField(max_length=254)

    def validate(self, attrs):
        name = attrs.get('name')
        if len(name) < 1:
            raise ValidationError({"name": ["Title cannot be blank."]})
        return attrs


class TaskRankListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRank
        fields = ('total_favorite_task', 'task', 'rank', 'id', 'is_favorite')

    task = serializers.SerializerMethodField()
    total_favorite_task = serializers.SerializerMethodField()

    def get_task(self, task_rank):
        request = self.context.get('request')
        queryset = self.context.get('q_set')
        return TaskListSerializer(task_rank.task, context={'request': request, 'queryset': queryset}).data

    def get_total_favorite_task(self, task_rank):
        request = self.context.get('request')
        return TaskRank.objects.filter(user=request.user, is_favorite=True).count()


class TaskRankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRank
        fields = ('task', 'rank', 'id', 'is_favorite', 'total_favorite_task')

    task = serializers.SerializerMethodField()
    total_favorite_task = serializers.SerializerMethodField()

    def get_task(self, task_rank):
        request = self.context.get('request')
        return TaskDetailSerializer(task_rank.task, context={'request': request}).data

    def get_total_favorite_task(self, task_rank):
        request = self.context.get('request')
        return TaskRank.objects.filter(user=request.user, is_favorite=True).count()


class TaskRankSwapSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    from_rank = serializers.IntegerField()
    to_rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        from_rank_id = attrs.get('from_rank')
        to_rank_id = attrs.get('to_rank')
        if not TaskRank.objects.filter(user=request.user, rank=from_rank_id).count():
            raise ValidationError({"from_rank": ["Invalid from rank id"]})
        if not TaskRank.objects.filter(user=request.user, rank=to_rank_id).count():
            raise ValidationError({"to_rank": ["Invalid to rank id"]})
        return attrs


# ############ Task Serializers END ############
class ProjectWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'name',
            'importance',
            'workflow',
        )

    workflow = serializers.SerializerMethodField()

    def get_workflow(self, obj):
        return WorkflowBasicSerializer(Workflow.objects.filter(project=obj)[:30], many=True).data


class RequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = '__all__'


class ProjectRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRank
        fields = (
            'project',
            'id',
            'rank',
        )
        read_only_fields = ('id',)

    rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        rank = ProjectRank.objects.filter(user=request.user).aggregate(Min('rank'), Max('rank'))
        if not rank['rank__min'] or not rank['rank__max']:
            raise ValidationError({"detail": "Invalid request"})
        if rank['rank__min'] > attrs['rank']:
            raise ValidationError(
                {
                    "detail": "Sorry! But the rank you chose is "
                    "lower than your total number"
                    " of project. please try again."
                }
            )
        if rank['rank__max'] < attrs['rank']:
            raise ValidationError(
                {
                    "detail": "Sorry! But the rank you chose "
                    "is greater than"
                    " your total number of project. "
                    "please try again."
                }
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('id', None)
        validated_data.pop('project', None)
        if self.context.get('request'):
            # re-arrange other project rank
            rerankProject(self)
        uobj = super(ProjectRankSerializer, self).update(instance, validated_data)
        return uobj


class ProjectRankChangeSerializer(serializers.ModelSerializer):
    drop_place = serializers.IntegerField(required=True)

    class Meta:
        model = ProjectRank
        fields = ('project', 'id', 'rank', 'drop_place')
        read_only_fields = ('id',)

    def validate(self, attrs):
        request = self.context.get('request')
        drop_place = ProjectRank.objects.filter(user=request.user, id=attrs.get('drop_place'))
        if drop_place:
            rank = drop_place[0].rank
            request.data['rank'] = rank
            attrs['rank'] = rank
        else:
            raise ValidationError({"detail": "Invalid request"})
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('id', None)
        validated_data.pop('project', None)
        if self.context.get('request'):
            # re-arrange other project rank
            rerankProject(self)
        uobj = super(ProjectRankChangeSerializer, self).update(instance, validated_data)
        return uobj


class WorkflowRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRank
        fields = (
            'workflow',
            'id',
            'rank',
        )
        read_only_fields = ('id',)

    rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        rank = WorkflowRank.objects.filter(user=request.user).aggregate(Min('rank'), Max('rank'))
        if not rank['rank__min'] or not rank['rank__max']:
            raise ValidationError({"detail": "Invalid request"})
        if rank['rank__min'] > attrs['rank']:
            raise ValidationError(
                {
                    "detail": "Sorry! But the rank you chose is "
                    "lower than your total number"
                    " of workflow. please try again."
                }
            )
        if rank['rank__max'] < attrs['rank']:
            raise ValidationError(
                {
                    "detail": "Sorry! But the rank you chose is "
                    "greater than"
                    " your total number of workflow. "
                    "please try again."
                }
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('id', None)
        validated_data.pop('workflow', None)
        if self.context.get('request'):
            # re-arrange other workflow rank
            rerankWorkflow(self)
        uobj = super(WorkflowRankSerializer, self).update(instance, validated_data)
        return uobj


class TaskRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRank
        fields = (
            'id',
            'is_favorite',
            'rank',
        )
        read_only_fields = ('id',)

    rank = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context.get('request')
        if len(attrs.keys()) > 1:
            raise ValidationError({"detail": "Invalid request"})
        if 'rank' in attrs.keys() and attrs.get('rank'):
            rank = TaskRank.objects.filter(user=request.user).exclude(rank=0).aggregate(Min('rank'), Max('rank'))
            if not rank['rank__min'] or not rank['rank__max']:
                raise ValidationError({"detail": "Invalid request"})
            if rank['rank__min'] > attrs['rank']:
                raise ValidationError(
                    {
                        "detail": "Sorry! But the rank you chose is "
                        "lower than your total number of task. "
                        "please try again."
                    }
                )
            if rank['rank__max'] < attrs['rank']:
                raise ValidationError(
                    {
                        "detail": "Sorry! But the rank you chose "
                        "is greater than"
                        " your total number of task. "
                        "please try again."
                    }
                )
            favourite_task = (
                TaskRank.objects.filter(user=request.user, is_favorite=True).exclude(rank=0).aggregate(Max('rank'))
            )
            if favourite_task['rank__max']:
                if attrs['rank'] <= favourite_task['rank__max']:
                    if favourite_task['rank__max'] >= 25:
                        TaskRank.objects.filter(
                            user=request.user, is_favorite=True, rank__gte=favourite_task['rank__max']
                        ).update(is_favorite=False)
                    attrs['is_favorite'] = True
                else:
                    attrs['is_favorite'] = False
            else:
                attrs['is_favorite'] = False

        elif 'is_favorite' in attrs.keys():
            if attrs.get('is_favorite'):
                if TaskRank.objects.filter(user=request.user, is_favorite=True).count() == 25:
                    raise ValidationError({"detail": "You already have selected top 25 tasks"})
                attrs['rank'] = 1
            else:
                attrs['rank'] = (
                    TaskRank.objects.filter(user=request.user, is_favorite=True)
                    .exclude(rank=0)
                    .aggregate(Max('rank'))['rank__max']
                )
        else:
            raise ValidationError({"detail": "Invalid request"})
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('task', None)
        validated_data.pop('id', None)
        if self.context.get('request'):
            # re-arrange other task rank
            rerankTask(self, validated_data)
        uobj = super(TaskRankSerializer, self).update(instance, validated_data)
        return uobj


class ServiceDeskUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskUserInformation
        fields = ('user_name',)


class AuditHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditHistory
        fields = (
            'model_reference',
            'model_id',
            'change_message',
            'created_at',
            'by_user',
            'to_user',
            'model_name',
            'last_importance',
            'old_due_date',
            'new_due_date',
            'by_servicedesk_user',
        )

    by_user = UserSerializer(read_only=True)
    by_servicedesk_user = ServiceDeskUserSerializer(read_only=True)

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['by_user'] = request.user
        return super(AuditHistorySerializer, self).create(validated_data)


class ServiceDeskAttachmentBasicSerializer(serializers.ModelSerializer):
    class Meta:

        model = ServiceDeskAttachment
        fields = (
            'id',
            'document_name',
            'document_url',
        )

    document_name = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    def get_document_name(self, obj):
        try:
            if obj.document_name:
                return obj.document_name
            return obj.document.name.split('/')[-1]
        except Exception as e:
            print("exception:", e)
            return obj.document.name if obj.document else ''

    def get_document_url(self, obj):
        try:
            return self.context['request'].build_absolute_uri(obj.document.url)
        except Exception as e:
            print("exception:", e)
            return obj.document.url


class ServiceDeskAttachmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskAttachment
        fields = (
            'document',
            'uploaded_by',
        )

    document = serializers.ListField(child=serializers.FileField(allow_empty_file=True, required=True))
    uploaded_by = serializers.EmailField(required=False, max_length=254)

    def validate(self, attrs):
        request = self.context.get('request')
        auth_token = request.data.get('auth', '').strip()
        if auth_token:
            old_instance = ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=False).first()
            if old_instance:
                attrs['uploaded_by'] = old_instance.user_email
            else:
                raise ValidationError({"detail": "Email doesn't exist"})
        else:
            raise ValidationError({"detail": "Invalid request"})
        return attrs

    def create(self, validated_data):
        document = validated_data.pop('document', [])
        uploaded_by = validated_data.pop('uploaded_by')

        def add_doc(doc):
            name = doc.name.split('.')[-1].lower()
            if (
                name
                in [
                    'docx',
                    'doc',
                    'rtf',
                    'txt',
                    'docm',
                    'xml',
                    'xlsx',
                    'xls',
                    'pdf',
                    'png',
                    'tif',
                    'csv',
                    'msg',
                    'jpg',
                    'pptx',
                    'gif',
                    'stl',
                ]
                or doc.size < 304857000
            ):
                doc_name = doc.name
                random_name = get_random_string(20) + "." + name
                doc.name = random_name
                return ServiceDeskAttachment(
                    document=doc, document_name=doc_name, uploaded_by=uploaded_by.lower().strip()
                )
            else:
                pass

        bulk_variable = list(map(add_doc, document))
        instance = ServiceDeskAttachment.objects.bulk_create(bulk_variable)
        return instance


class ServiceDeskUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskUserInformation
        fields = (
            'user_name',
            'user_email',
            'user_phone_number',
            'title',
        )
        extra_kwargs = {
            'user_email': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this email field",
                },
            },
            'user_name': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this name field",
                },
            },
        }

    user_phone_number = serializers.CharField(required=False)

    def validate(self, attrs):
        attrs['organization'] = Organization.objects.first()
        if attrs.get('user_phone_number'):
            user_phone_number = attrs.get('user_phone_number')
            if len(user_phone_number) not in range(9, 13):
                raise ValidationError({"phone number": ["Invalid phone number."]})
        attrs['user_email'] = attrs['user_email'].lower().strip()
        return attrs


class ServiceDeskRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'subject',
            'description',
            'requested_due_date',
            'attachments',
            'assigned_to',
            'request_priority',
        )
        extra_kwargs = {
            'subject': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this subject field",
                },
            },
            'description': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this description field",
                },
            },
        }

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )

    def validate(self, attrs):
        request = self.context.get('request')
        auth_token = request.data.get('auth').strip()
        user_instance = ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=False).first()
        if user_instance:
            attrs['user_information'] = user_instance
        else:
            raise ValidationError({"detail": "Invalid token"})
        attachments = attrs.pop('attachments', [])
        attrs['attachments'] = []
        for attach_id in attachments:
            try:
                attachment = ServiceDeskAttachment.objects.get(
                    id=attach_id, uploaded_by=user_instance.user_email, can_remove=True, is_delete=False
                )
            except ServiceDeskAttachment.DoesNotExist:
                raise ValidationError({"detail": "Document doesn't exist"})
            attrs['attachments'].append(attachment)
        return attrs

    def create(self, validated_data):
        attachments = validated_data.pop('attachments', [])
        instance = super(ServiceDeskRequestCreateSerializer, self).create(validated_data)
        if attachments:
            for attachment in attachments:
                attachment.can_remove = False
                attachment.service_desk_request = instance
                attachment.save()
        return instance


class RequestAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'document_name',
            'document_url',
            'uploaded_by',
            'created_at',
        )

    document_name = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()
    uploaded_by = ServiceDeskUserSerializer()

    def get_document_name(self, obj):
        try:
            if obj.document_name:
                return obj.document_name
            return obj.document.name.split('/')[-1]
        except Exception as e:
            print("exception:", str(e))
            return obj.document.name if obj.document else ''

    def get_document_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.document.url)


class ServiceDeskUserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskUserInformation
        fields = (
            'user_name',
            'user_email',
            'user_phone_number',
            'title',
        )


class RequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'id',
            'request_priority',
            'subject',
            'requested_due_date',
            'user_information',
            'assigned_to',
            'attachments',
            'description',
        )

    user_information = ServiceDeskUserBasicSerializer()
    attachments = serializers.SerializerMethodField()

    def get_attachments(self, obj):
        request = self.context['request']
        contenttype_obj = ContentType.objects.get_for_model(obj)
        return RequestAttachmentSerializer(
            Attachment.objects.filter(content_type=contenttype_obj, object_id=obj.id, is_delete=False),
            many=True,
            context={'request': request},
        ).data


class RequestDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'id',
            'request_priority',
            'user_information',
            'description',
            'subject',
            'attachments',
            'requested_due_date',
            'assigned_to',
        )

    attachments = serializers.SerializerMethodField()
    user_information = ServiceDeskUserDetailSerializer()

    def get_attachments(self, obj):
        request = self.context['request']
        contenttype_obj = ContentType.objects.get_for_model(obj)
        return RequestAttachmentSerializer(
            Attachment.objects.filter(content_type=contenttype_obj, object_id=obj.id, is_delete=False),
            many=True,
            context={'request': request},
        ).data


class ServiceDeskListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'id',
            'subject',
            'assigned_to',
            'status',
        )

    status = serializers.CharField(read_only=True, default='Submitted')


class ServiceDeskDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'id',
            'subject',
            'description',
            'assigned_to',
            'status',
            'request_priority',
            'documents',
            'requested_due_date',
        )

    status = serializers.CharField(read_only=True, default='Submitted')
    documents = serializers.SerializerMethodField()

    def get_documents(self, obj):
        return ServiceDeskAttachmentBasicSerializer(
            ServiceDeskAttachment.objects.filter(service_desk_request=obj, can_remove=False, is_delete=True), many=True
        ).data


class ServiceDeskTaskAttachmentSerializer(serializers.ModelSerializer):
    class Meta:

        model = Attachment
        fields = (
            'document_name',
            'document_url',
            'created_at',
            'created_by',
        )

    document_name = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    def get_document_name(self, obj):
        try:
            if obj.document_name:
                return obj.document_name
            return obj.document.name.split('/')[-1]
        except Exception as e:
            print("exception:", str(e))
            return obj.document.name if obj.document else None

    def get_document_url(self, obj):
        try:
            return self.context['request'].build_absolute_uri(obj.document.url)
        except Exception as e:
            print("exception:", str(e))
            return obj.document.url

    def get_created_by(self, obj):
        if obj.created_by:
            return obj.created_by.first_name + " " + obj.created_by.last_name
        elif obj.uploaded_by:
            return obj.uploaded_by.user_name
        else:
            return None


class RequestTaskDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = (
            'id',
            'user_information',
        )

    user_information = ServiceDeskUserBasicSerializer()


class UserNameSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(source='full_name')

    class Meta:
        model = User
        fields = ('fullname',)

    def to_representation(self, instance):
        return instance.full_name()


class ServiceDeskTaskListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'name',
            'assigned_to',
            'assigned_to_group',
            'status',
            'servicedeskrequest_details',
        )

    assigned_to = serializers.SerializerMethodField()
    assigned_to_group = serializers.SerializerMethodField()
    servicedeskrequest_details = serializers.SerializerMethodField()

    def get_assigned_to(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.first_name + " " + obj.assigned_to.last_name
        return None

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_servicedeskrequest_details(self, obj):
        return RequestTaskListSerializer(ServiceDeskExternalRequest.objects.filter(task=obj).first()).data


class ServiceDeskProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'name',
            'assigned_to_users',
            'assigned_to_group',
            'status',
            'servicedeskrequest_details',
        )

    assigned_to_users = UserNameSerializer(many=True)
    assigned_to_group = serializers.SerializerMethodField()
    servicedeskrequest_details = serializers.SerializerMethodField()

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_servicedeskrequest_details(self, obj):
        return RequestTaskListSerializer(ServiceDeskExternalRequest.objects.filter(project=obj).first()).data


class ServiceDeskWorkflowListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'name',
            'assigned_to_users',
            'assigned_to_group',
            'status',
            'servicedeskrequest_details',
        )

    assigned_to_users = UserNameSerializer(many=True)
    assigned_to_group = serializers.SerializerMethodField()
    servicedeskrequest_details = serializers.SerializerMethodField()

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_servicedeskrequest_details(self, obj):
        return RequestTaskListSerializer(ServiceDeskExternalRequest.objects.filter(workflow=obj).first()).data


class TaskServiceDeskExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'task',
            'replies',
        )

    task = ServiceDeskTaskListSerializer()


class WorkflowExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'workflow',
            'replies',
        )

    workflow = ServiceDeskWorkflowListSerializer()


class ProjectServiceDeskExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'project',
            'replies',
        )

    project = ServiceDeskProjectListSerializer()


class ServiceDeskExternalRequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'project',
            'workflow',
            'task',
        )

    def to_representation(self, instance):
        if instance.task:
            return TaskServiceDeskExternalRequestSerializer(instance).data
        elif instance.project:
            return ProjectServiceDeskExternalRequestSerializer(instance).data
        elif instance.workflow:
            return WorkflowExternalRequestSerializer(instance).data
        else:
            return None


class ServiceDeskTaskDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'name',
            'importance',
            'assigned_to',
            'assigned_to_group',
            'status',
            'due_date',
            'description',
            'attachments',
        )

    attachments = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    assigned_to_group = serializers.SerializerMethodField()

    def get_assigned_to(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.first_name + " " + obj.assigned_to.last_name
        return None

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_attachments(self, obj):
        return ServiceDeskTaskAttachmentSerializer(
            Attachment.objects.filter(task=obj, is_delete=False), many=True
        ).data


class ServiceDeskProjectDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'name',
            'importance',
            'assigned_to_users',
            'assigned_to_group',
            'status',
            'due_date',
            'description',
            'attachments',
            'servicedeskrequest_details',
        )

    attachments = serializers.SerializerMethodField()
    assigned_to_users = UserNameSerializer(many=True)
    assigned_to_group = serializers.SerializerMethodField()
    servicedeskrequest_details = serializers.SerializerMethodField()

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_attachments(self, obj):
        return ServiceDeskTaskAttachmentSerializer(
            Attachment.objects.filter(project=obj, is_delete=False), many=True
        ).data

    def get_servicedeskrequest_details(self, obj):
        return ServiceDeskRequestSerializer(ServiceDeskExternalRequest.objects.filter(project=obj).first()).data


class ServiceDeskWorkflowDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'name',
            'importance',
            'assigned_to_users',
            'assigned_to_group',
            'status',
            'due_date',
            'description',
            'attachments',
            'servicedeskrequest_details',
        )

    attachments = serializers.SerializerMethodField()
    assigned_to_users = UserNameSerializer(many=True)
    assigned_to_group = serializers.SerializerMethodField()
    servicedeskrequest_details = serializers.SerializerMethodField()

    def get_assigned_to_group(self, obj):
        if obj.assigned_to_group:
            return obj.assigned_to_group.all().values_list('name', flat=True)
        return None

    def get_attachments(self, obj):
        return ServiceDeskTaskAttachmentSerializer(
            Attachment.objects.filter(workflow=obj, is_delete=False), many=True
        ).data

    def get_servicedeskrequest_details(self, obj):
        return ServiceDeskRequestSerializer(ServiceDeskExternalRequest.objects.filter(workflow=obj).first()).data


class TaskDetailExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'task',
        )

    task = ServiceDeskTaskDetailSerializer()


class WorkflowDetailExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'workflow',
        )

    workflow = ServiceDeskWorkflowDetailSerializer()


class ProjectDetailExternalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'id',
            'service_desk_request',
            'project',
        )

    project = ServiceDeskProjectDetailSerializer()


class ServiceDeskExternalRequestDetailSerializer(serializers.Serializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'project',
            'workflow',
            'task',
        )

    def to_representation(self, instance):
        if instance.task:
            return TaskDetailExternalRequestSerializer(instance).data
        elif instance.project:
            return ProjectDetailExternalRequestSerializer(instance).data
        elif instance.workflow:
            return WorkflowDetailExternalRequestSerializer(instance).data
        else:
            return None


class AssociateNewRequestSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    user_name = serializers.CharField(max_length=254, required=True)
    user_email = serializers.EmailField(required=True, max_length=254)
    description = serializers.CharField(required=True, max_length=10000000)
    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    cc = serializers.ListField(required=False, child=serializers.EmailField(required=False))


class ProjectMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'project',
            'message',
            'attachments',
            'is_external_message',
            'is_internal_message',
        )
        extra_kwargs = {"project": {"required": True}, "message": {"required": False}}

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    is_external_message = serializers.BooleanField(required=True)
    is_internal_message = serializers.BooleanField(required=True)

    def validate(self, attrs):
        if attrs['is_external_message'] == attrs['is_internal_message']:
            raise ValidationError({"detail": "Invalid request"})
        if not attrs.get('message') and not attrs.get('attachments'):
            raise ValidationError({"detail": "This message Can not be send."})
        if not attrs.get('project'):
            raise ValidationError({"detail": "Invalid project."})
        return attrs


class WorkflowMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'workflow',
            'message',
            'attachments',
            'is_external_message',
            'is_internal_message',
        )
        extra_kwargs = {"workflow": {"required": True}, "message": {"required": False}}

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    is_external_message = serializers.BooleanField(required=True)
    is_internal_message = serializers.BooleanField(required=True)

    def validate(self, attrs):
        if attrs['is_external_message'] == attrs['is_internal_message']:
            raise ValidationError({"detail": "Invalid request"})
        if not attrs.get('message') and not attrs.get('attachments'):
            raise ValidationError({"detail": "This message Can not be send."})
        if not attrs.get('workflow'):
            raise ValidationError({"detail": "Invalid workflow."})
        return attrs


class TaskMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'task',
            'message',
            'attachments',
            'is_external_message',
            'is_internal_message',
            'request_id',
            'cc',
        )
        extra_kwargs = {"task": {"required": True}, "message": {"required": False}}

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    is_external_message = serializers.BooleanField(required=True)
    is_internal_message = serializers.BooleanField(required=True)
    request_id = serializers.IntegerField(min_value=1, required=False)
    cc = serializers.ListField(required=False, child=serializers.EmailField(required=False))

    def validate(self, attrs):
        if attrs['is_external_message'] == attrs['is_internal_message']:
            raise ValidationError({"detail": "Invalid request"})
        if not attrs.get('message') and not attrs.get('attachments'):
            raise ValidationError({"detail": "This message Can not be send."})
        if not attrs.get('task'):
            raise ValidationError({"detail": "Invalid task."})
        if attrs['is_external_message'] and not attrs.get('request_id'):
            raise ValidationError({"detail": "External request id is required."})
        return attrs


class MessageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'id',
            'message',
            'created_by_user',
            'reply_by_servicedeskuser',
            'created_at',
            'attachments',
            'servicedesk_user_detail',
        )

    created_by_user = serializers.SerializerMethodField()
    reply_by_servicedeskuser = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    servicedesk_user_detail = serializers.SerializerMethodField()

    def get_created_by_user(self, obj):
        if obj.created_by_user:
            return UserSerializer(obj.created_by_user, context={'request': self.context.get('request')}).data
        return None

    def get_reply_by_servicedeskuser(self, obj):
        if obj.reply_by_servicedeskuser:
            return ServiceDeskUserBasicSerializer(obj.reply_by_servicedeskuser).data
        return None

    def get_attachments(self, obj):
        request = self.context['request']
        return DocumentDetailsSerializer(
            Attachment.objects.filter(message_document=obj, is_delete=False), many=True, context={'request': request}
        ).data

    def get_servicedesk_user_detail(self, obj):
        if obj.is_external_message:
            if obj.project:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            project=obj.project, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(project=obj.project).first().servicedeskuser
                    ).data
            elif obj.workflow:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            workflow=obj.workflow, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(workflow=obj.workflow).first().servicedeskuser
                    ).data
            elif obj.task:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            task=obj.task, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(task=obj.task).first().servicedeskuser
                    ).data
            else:
                return None
        else:
            return None


class ServiceDeskRequestDocumentUploadSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    attachments = serializers.ListField(
        required=True,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )


class PendingRequestMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'servicedesk_request',
            'message',
        )
        extra_kwargs = {"servicedesk_request": {"required": True}, "message": {"required": True}}


class SubmitRequestMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'message',
            'request_id',
            'attachments',
        )
        extra_kwargs = {"request_id": {"required": True}, "message": {"required": False}}

    attachments = serializers.ListField(
        required=False,
        child=serializers.IntegerField(
            min_value=1,
        ),
    )
    request_id = serializers.IntegerField(min_value=1, required=True)

    def validate(self, attrs):
        if not attrs.get('message') and not attrs.get('attachments'):
            raise ValidationError({"detail": "This message Can not be send."})
        if not attrs.get('request_id'):
            raise ValidationError({"detail": "Invalid request id."})
        return attrs


class PrivielgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Privilage_Change_Log
        fields = (
            'category_type',
            'new_privilege',
            'project',
            'task',
            'workflow',
            'team_member',
            'changed_at',
        )

    def to_representation(self, instance):
        if instance.task:
            name = instance.task.name
        elif instance.workflow:
            name = instance.workflow.name
        elif instance.project:
            name = instance.project.name
        else:
            name = ''
        member_name = str(instance.team_member.first_name + " " + instance.team_member.last_name)
        return {
            'CATEGORY': instance.category_type.upper(),
            'NAME': name,
            'TEAM MEMBER': member_name,
            'PRIVILEGE': ' , '.join(instance.new_privilege),
        }


class TagReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagChangeLog
        fields = (
            'category_type',
            'tag_name',
            'active',
            'complete',
        )

    active = serializers.IntegerField(default=0)
    complete = serializers.IntegerField(default=0)
    tag_name = serializers.SerializerMethodField()

    def get_tag_name(self, obj):
        return str(obj['tag_reference__tag'])


class OpenTagReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagChangeLog
        fields = (
            'tag_name',
            'open_project',
            'open_workflow',
            'open_task',
            'total',
        )

    open_project = serializers.IntegerField(default=0)
    open_workflow = serializers.IntegerField(default=0)
    open_task = serializers.IntegerField(default=0)
    total = serializers.IntegerField(default=0)
    tag_name = serializers.SerializerMethodField()

    def get_tag_name(self, obj):
        return str(obj['tag_reference__tag'])


class CompletedTagReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagChangeLog
        fields = (
            'tag_name',
            'completed_project',
            'completed_workflow',
            'completed_task',
            'total',
        )

    completed_project = serializers.IntegerField(default=0)
    completed_workflow = serializers.IntegerField(default=0)
    completed_task = serializers.IntegerField(default=0)
    total = serializers.IntegerField(default=0)
    tag_name = serializers.SerializerMethodField()

    def get_tag_name(self, obj):
        return str(obj['tag_reference__tag'])


class GroupWorkLoadLogReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupWorkLoadLog
        fields = (
            'category_type',
            'work_group_name',
            'active',
            'complete',
        )

    active = serializers.IntegerField(default=0)
    complete = serializers.IntegerField(default=0)
    work_group_name = serializers.SerializerMethodField()

    def get_work_group_name(self, obj):
        return str(obj['work_group__name'])


class OpenGroupWorkLoadReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupWorkLoadLog
        fields = (
            'work_group_name',
            'open_project',
            'open_workflow',
            'open_task',
            'total',
        )

    open_project = serializers.IntegerField(default=0)
    open_workflow = serializers.IntegerField(default=0)
    open_task = serializers.IntegerField(default=0)
    total = serializers.IntegerField(default=0)
    work_group_name = serializers.SerializerMethodField()

    def get_work_group_name(self, obj):
        return str(obj['work_group__name'])


class CompletedGroupWorkLoadReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupWorkLoadLog
        fields = (
            'work_group_name',
            'completed_project',
            'completed_workflow',
            'completed_task',
            'total',
        )

    completed_project = serializers.IntegerField(default=0)
    completed_workflow = serializers.IntegerField(default=0)
    completed_task = serializers.IntegerField(default=0)
    total = serializers.IntegerField(default=0)
    work_group_name = serializers.SerializerMethodField()

    def get_work_group_name(self, obj):
        return str(obj['work_group__name'])


class TeamMemberWorkLoadReportFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMemberWorkLoadLog
        fields = (
            'team_member',
            'category_type',
            'total_count',
        )

    team_member = serializers.SerializerMethodField()
    total_count = serializers.IntegerField()

    def get_team_member(self, obj):
        return UserBasicSerializer(User.objects.get(id=obj['team_member'])).data


class TeamMemberWorkLoadReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMemberWorkLoadLog
        fields = (
            'team_member',
            'project',
            'workflow',
            'task',
            'total',
        )

    team_member = serializers.SerializerMethodField()
    project = serializers.IntegerField()
    workflow = serializers.IntegerField()
    task = serializers.IntegerField()
    total = serializers.IntegerField()

    def get_team_member(self, obj):
        return UserBasicSerializer(User.objects.get(id=obj['team_member'])).data


class EfficiencyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompletionLog
        fields = (
            'team_member',
            'project_avg',
            'workflow_avg',
            'task_avg',
        )

    project_avg = serializers.IntegerField(default=0)
    workflow_avg = serializers.IntegerField(default=0)
    task_avg = serializers.IntegerField(default=0)
    team_member = serializers.SerializerMethodField()

    def get_team_member(self, obj):
        return UserBasicSerializer(User.objects.get(id=int(obj['team_member']))).data


class EfficiencyReportFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompletionLog
        fields = (
            'created_on',
            'completed_on',
            'completion_time',
            'category_type',
            'name',
            'team_member',
        )

    name = serializers.SerializerMethodField()
    team_member = serializers.SerializerMethodField()
    completed_on = serializers.DateField(format=DATE_FORMAT_OUT)
    created_on = serializers.DateField(format=DATE_FORMAT_OUT)

    def get_team_member(self, obj):
        return str(obj.team_member.first_name + " " + obj.team_member.last_name)

    def get_name(self, obj):
        if obj.project:
            return str(obj.project.name)
        if obj.workflow:
            return str(obj.workflow.name)
        if obj.task:
            return str(obj.task.name)


class ProductivityReportFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkProductivityLog
        fields = (
            'team_member',
            'category_type',
            'active',
            'completed',
        )

    active = serializers.IntegerField(default=0)
    completed = serializers.IntegerField(default=0)
    team_member = serializers.SerializerMethodField()

    def get_team_member(self, obj):
        return UserBasicSerializer(User.objects.get(id=int(obj['team_member']))).data


class ProductivityReporGraphSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkProductivityLog
        fields = ('created_on', 'project', 'workflow', 'task')

    project = serializers.IntegerField(default=0)
    workflow = serializers.IntegerField(default=0)
    task = serializers.IntegerField(default=0)


class ProductivityReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkProductivityLog
        fields = (
            'team_member',
            'active',
            'complete',
        )

    active = serializers.IntegerField(default=0)
    complete = serializers.IntegerField(default=0)
    team_member = serializers.SerializerMethodField()

    def get_team_member(self, obj):
        return UserBasicSerializer(User.objects.get(id=obj['team_member'])).data


class ProductivityReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkProductivityLog
        fields = ('category_type', 'new', 'completed', 'name', 'team_member', 'work_group')

    name = serializers.SerializerMethodField()
    team_member = serializers.SerializerMethodField()
    work_group = serializers.SerializerMethodField()

    def get_team_member(self, obj):
        if obj.team_member:
            return str(obj.team_member.first_name + " " + obj.team_member.last_name)
        else:
            return None

    def get_name(self, obj):
        if obj.project:
            return str(obj.project.name)
        if obj.workflow:
            return str(obj.workflow.name)
        if obj.task:
            return str(obj.task.name)

    def get_work_group(self, obj):
        if obj.work_group:
            return str(obj.work_group.name)


class GlobalSearchProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'name',
            'owner',
            'assigned_to_users',
            'importance',
            'due_date',
            'task',
        )

    owner = UserBasicSerializer()
    assigned_to_users = UserSerializer(many=True)
    task = serializers.SerializerMethodField()

    def get_task(self, project_obj):
        task_qset = self.context.get("task_qset")
        if project_obj.workflow_assigned_project.all().exists():
            date_today = datetime.datetime.utcnow().date()
            workflow = project_obj.workflow_assigned_project.all().values_list('id', flat=True)[::1]
            tasks = task_qset.filter(workflow_id__in=workflow)
            data = {
                'total_task': tasks.count(),
                'completed_task': tasks.filter(status__in=[3, 4]).count(),
                'passed_due': tasks.filter(due_date__date__lt=date_today).exclude(status__in=[3, 4]).count(),
            }
            return data
        return None


class WorkflowOwnerUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'first_name',
            'last_name',
            'user_avatar',
        )


class GlobalSearchWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = (
            'id',
            'name',
            'importance',
            'owner',
            'due_date',
            'total_task',
            'completed_task',
        )

    owner = WorkflowOwnerUserSerializer()
    due_date = serializers.DateTimeField()
    total_task = serializers.SerializerMethodField()
    completed_task = serializers.SerializerMethodField()

    def get_total_task(self, workflow_obj):
        task_qset = self.context.get("task_qset")
        return task_qset.filter(workflow=workflow_obj).count()

    def get_completed_task(self, workflow_obj):
        task_qset = self.context.get("task_qset")
        return task_qset.filter(workflow=workflow_obj, status__in=[3, 4]).count()


class GlobalSearchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'assigned_to',
            'importance',
            'due_date',
            'is_private',
        )

    assigned_to = UserSerializer()


class MessageDeleteSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    message_id = serializers.IntegerField(required=True)


class ShareDocumentSerializer(serializers.Serializer):
    class Meta:
        fields = '__all__'

    document_id = serializers.IntegerField(required=True, allow_null=False)
    email = serializers.ListField(required=True, child=serializers.EmailField(allow_null=False, required=True))


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequestMessage
        fields = (
            'id',
            'message',
            'created_by_user',
            'reply_by_servicedeskuser',
            'created_at',
            'attachments',
            'servicedesk_user_detail',
            'cc',
        )

    created_by_user = serializers.SerializerMethodField()
    reply_by_servicedeskuser = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    servicedesk_user_detail = serializers.SerializerMethodField()
    cc = serializers.SerializerMethodField()

    def get_created_by_user(self, obj):
        if obj.created_by_user:
            return UserSerializer(obj.created_by_user, context={'request': self.context.get('request')}).data
        return None

    def get_reply_by_servicedeskuser(self, obj):
        if obj.reply_by_servicedeskuser:
            return ServiceDeskUserBasicSerializer(obj.reply_by_servicedeskuser).data
        return None

    def get_attachments(self, obj):
        request = self.context['request']
        return DocumentDetailsSerializer(
            Attachment.objects.filter(message_document=obj, is_delete=False), many=True, context={'request': request}
        ).data

    def get_servicedesk_user_detail(self, obj):
        if obj.is_external_message:
            if obj.project:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            project=obj.project, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(project=obj.project).first().servicedeskuser
                    ).data
            elif obj.workflow:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            workflow=obj.workflow, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(workflow=obj.workflow).first().servicedeskuser
                    ).data
            elif obj.task:
                if obj.servicedesk_request:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(
                            task=obj.task, service_desk_request=obj.servicedesk_request
                        )
                        .first()
                        .servicedeskuser
                    ).data
                else:
                    return ServiceDeskUserBasicSerializer(
                        ServiceDeskExternalRequest.objects.filter(task=obj.task).first().servicedeskuser
                    ).data
            else:
                return None
        else:
            return None

    def get_cc(self, obj):
        if ServiceDeskExternalCCUser.objects.filter(message=obj).exists():
            cc_user = []
            [
                cc_user.append(
                    {
                        'email': email,
                        "user_name": ServiceDeskUserInformation.objects.filter(user_email=email).first().user_name,
                    }
                )
                if ServiceDeskUserInformation.objects.filter(user_email=email).exists()
                else cc_user.append({'email': email, "user_name": ""})
                for email in ServiceDeskExternalCCUser.objects.filter(message=obj).values_list('email', flat=True)[::1]
            ]
            return cc_user
        return None
