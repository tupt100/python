from django.contrib import admin
from django.db import connection
from projects.globalcustomfields.admin import *  # noqa
from projects.models import (
    Attachment,
    AuditHistory,
    AWSCredential,
    CompletionLog,
    GroupWorkLoadLog,
    PageInstruction,
    Privilage_Change_Log,
    Project,
    ProjectRank,
    Request,
    ServiceDeskAttachment,
    ServiceDeskExternalCCUser,
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskRequestMessage,
    ServiceDeskUserInformation,
    Tag,
    TagChangeLog,
    TaskRank,
    TeamMemberWorkLoadLog,
    WorkflowRank,
    WorkGroup,
    WorkGroupMember,
    WorkProductivityLog,
)
from projects.tasksapp.admin import *  # noqa
from projects.templates.admin import *  # noqa


class ProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "owner", "due_date", "status", "importance", "task_importance"]
    list_filter = ["organization", "status"]
    search_fields = ["id", "name"]


class RequestAdmin(admin.ModelAdmin):
    list_display = ["request_by", "due_date", "importance", "description"]


class AttachmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "external_url",
        "document_name",
        "content_type",
        "object_id",
        "content_object",
        "task",
        "project",
        "workflow",
        'is_delete',
    ]
    list_filter = ('is_delete',)


class ProjectRankAdmin(admin.ModelAdmin):
    list_display = ["user", "project", "project_id", "rank"]
    list_filter = ["user", "is_active"]


class WorkflowRankAdmin(admin.ModelAdmin):
    list_display = ["user", "workflow", "workflow_id", "rank"]
    list_filter = ["user", "is_active"]


class TaskRankAdmin(admin.ModelAdmin):
    list_display = ["user", "task", "task_id", "rank", "is_favorite"]
    list_filter = ["user", "is_active", "is_favorite"]


class AuditHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "model_reference",
        "model_id",
        "by_user",
        "change_message",
        "model_name",
        "last_importance",
        "old_due_date",
        "new_due_date",
    ]
    list_filter = ["model_reference"]


class TagAdmin(admin.ModelAdmin):
    list_display = ["tag", "organization"]
    list_filter = ["organization"]


class WorkGroupAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "organization",
    ]
    list_filter = ["organization", "name", "group_members"]


class WorkGroupMemberAdmin(admin.ModelAdmin):
    list_display = ["id", "group_member", "work_group"]
    list_filter = ["work_group", "group_member", "work_group"]


class ServiceDeskAttachmentAdmin(admin.ModelAdmin):
    fields = ["document", "document_name", "uploaded_by", "service_desk_request", "can_remove"]
    list_display = [
        "document_name",
    ]
    list_filter = [
        "uploaded_by",
    ]


class ServiceDeskUserInformationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user_name",
        "user_email",
    ]
    list_filter = [
        "user_email",
        "is_expire",
    ]


class ServiceDeskRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "subject",
        "request_priority",
        "assigned_to",
        "user_information",
    ]
    list_filter = [
        "is_delete",
        "user_information",
    ]


class ServiceDeskExternalRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "task",
        "project",
        "workflow",
        "servicedeskuser",
    ]
    list_filter = [
        "task",
        "project",
        "workflow",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ServiceDeskRequestMessageAdmin(admin.ModelAdmin):
    fields = (
        'message',
        'created_by_user',
        'reply_by_servicedeskuser',
        'servicedesk_request',
    )
    list_display = [
        "id",
        "message",
        "is_first_message",
        "project",
        "task",
        "workflow",
        "servicedesk_request",
    ]
    list_filter = [
        "project",
        "task",
        "workflow",
        "servicedesk_request",
        "is_first_message",
    ]


class Privilage_Change_Log_Admin(admin.ModelAdmin):
    fields = ("category_type", "project", "task", "workflow", "team_member", "changed_by", "changed_at")
    list_display = [
        "id",
        "category_type",
        "team_member",
        "new_privilege",
        "project",
        "task",
        "workflow",
        "team_member",
        "changed_at",
        "changed_by",
    ]
    list_filter = [
        "project",
        "task",
        "workflow",
        "team_member",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class Tag_Change_Log_Admin(admin.ModelAdmin):
    fields = (
        "category_type",
        "tag_reference",
        "project",
        "task",
        "workflow",
        "new",
        "completed",
        "changed_at",
    )
    list_display = [
        "category_type",
        "tag_reference",
        "project",
        "task",
        "workflow",
        "new",
        "completed",
        "changed_at",
    ]
    list_filter = [
        "tag_reference",
        "category_type",
        "project",
        "task",
        "workflow",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class GroupWorkLoadLogAdmin(admin.ModelAdmin):
    fields = (
        "category_type",
        "work_group",
        "project",
        "task",
        "workflow",
        "new",
        "completed",
        "changed_at",
    )
    list_display = [
        "category_type",
        "work_group",
        "project",
        "task",
        "workflow",
        "new",
        "completed",
        "changed_at",
    ]
    list_filter = [
        "work_group",
        "category_type",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TeamMemberWorkLoadLogAdmin(admin.ModelAdmin):
    fields = (
        "category_type",
        "team_member",
        "project",
        "task",
        "workflow",
        "new",
        "changed_at",
    )
    list_display = [
        "category_type",
        "team_member",
        "project",
        "task",
        "workflow",
        "new",
        "changed_at",
    ]
    list_filter = [
        "team_member",
        "category_type",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CompletionLogAdmin(admin.ModelAdmin):
    fields = (
        "category_type",
        "team_member",
        "project",
        "task",
        "workflow",
        "completion_time",
        "created_on",
        "completed_on",
    )
    list_display = [
        "category_type",
        "team_member",
        "project",
        "task",
        "workflow",
        "completion_time",
        "created_on",
        "completed_on",
    ]
    list_filter = [
        "team_member",
        "category_type",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkProductivityLogAdmin(admin.ModelAdmin):
    fields = (
        "category_type",
        "new",
        "completed",
        "team_member",
        "work_group",
        "project",
        "task",
        "workflow",
        "created_on",
    )
    list_display = [
        "category_type",
        "new",
        "completed",
        "team_member",
        "work_group",
        "project",
        "task",
        "workflow",
        "created_on",
    ]
    list_filter = [
        "team_member",
        "work_group",
        "category_type",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ServiceDeskExternalCCUserAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "email",
        "message",
        "external_request",
        "created_by",
    ]
    list_filter = [
        "email",
        "external_request",
    ]


class AWSCredentialAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "bucket_name",
        "kms_key",
    ]

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        user = request.user
        if user.is_superuser and connection.schema_name != 'public' and AWSCredential.objects.count() == 0:
            return True
        else:
            return False


admin.site.register(ServiceDeskExternalRequest, ServiceDeskExternalRequestAdmin)
admin.site.register(ServiceDeskRequest, ServiceDeskRequestAdmin)
admin.site.register(ServiceDeskUserInformation, ServiceDeskUserInformationAdmin)
admin.site.register(ServiceDeskAttachment, ServiceDeskAttachmentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(AuditHistory, AuditHistoryAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Request, RequestAdmin)
admin.site.register(PageInstruction)
admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(TaskRank, TaskRankAdmin)
admin.site.register(WorkflowRank, WorkflowRankAdmin)
admin.site.register(ProjectRank, ProjectRankAdmin)
admin.site.register(WorkGroup, WorkGroupAdmin)
admin.site.register(WorkGroupMember, WorkGroupMemberAdmin)
admin.site.register(ServiceDeskRequestMessage, ServiceDeskRequestMessageAdmin)
admin.site.register(Privilage_Change_Log, Privilage_Change_Log_Admin)
admin.site.register(TagChangeLog, Tag_Change_Log_Admin)
admin.site.register(GroupWorkLoadLog, GroupWorkLoadLogAdmin)
admin.site.register(TeamMemberWorkLoadLog, TeamMemberWorkLoadLogAdmin)
admin.site.register(CompletionLog, CompletionLogAdmin)
admin.site.register(WorkProductivityLog, WorkProductivityLogAdmin)
admin.site.register(ServiceDeskExternalCCUser, ServiceDeskExternalCCUserAdmin)
admin.site.register(AWSCredential, AWSCredentialAdmin)
