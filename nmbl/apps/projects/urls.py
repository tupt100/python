from django.urls import path
from rest_framework import routers

from .api.views import (
    TaskFixtureViewSet,
    TaskRankViewSet,
    TaskStatisticsViewSet,
    TaskViewSet,
    WorkflowFixtureViewSet,
)
from .views import (
    AttachmentCopyOrMoveView,
    AttachmentViewSet,
    AuditHistoryViewSet,
    CeleryDrainViewSet,
    CompanyWorkGroupViewSet,
    CustomFieldViewSet,
    DashboardStatisticsViewSet,
    EfficiencyReportViewSet,
    GlobalCustomFieldValueViewSet,
    GlobalCustomFieldViewSet,
    GlobalSearchViewSet,
    GroupWorkLoadReportViewSet,
    PendingRequestViewSet,
    PrivilegeReportViewSet,
    ProductivityReportViewSet,
    ProjectRankChangeViewSet,
    ProjectRankViewSet,
    ProjectStatisticsViewSet,
    ProjectTemplateCustomFieldViewSet,
    ProjectTemplateViewSet,
    ProjectViewSet,
    RequestPortalViewSet,
    ReSendServiceDeskLinkAPIView,
    ServiceDeskAttachmentViewSet,
    ServiceDeskRequestMessageViewSet,
    ServiceDeskTokenVerificationAPIView,
    ServiceDeskUserViewSet,
    ShareDocumentViewSet,
    SubmitServiceDeskRequestViewSet,
    SubmittedRequestViewSet,
    TagReportViewSet,
    TagViewSet,
    TaskTemplateViewSet,
    TeamMemberWorkLoadReportViewSet,
    UserWorkGroupViewSet,
    WorkflowRankViewSet,
    WorkflowStatisticsViewSet,
    WorkflowTemplateCustomFieldViewSet,
    WorkflowTemplateViewSet,
    WorkflowViewSet,
    WorkGroupMemberViewSet,
    WorkGroupViewSet,
)
from .views_webhook import (
    PostmarkCommonWebHook,
    PostmarkProjectWebHook,
    PostmarkTaskWebHook,
    TemplateTestView,
)

app_name = 'projects'

router = routers.DefaultRouter()
router.register('api/documents', AttachmentViewSet, base_name='document'),
router.register('api/projects', ProjectViewSet, base_name='project'),
router.register('api/workflows', WorkflowViewSet, base_name='workflow'),
router.register('api/workflow-fixtures', WorkflowFixtureViewSet, base_name='workflow-fixture'),
router.register('api/tasks', TaskViewSet, base_name='task'),
router.register('api/task-fixtures', TaskFixtureViewSet, base_name='task_fixtures'),
router.register('api/tasks_statistic', TaskStatisticsViewSet, base_name='task_statistic'),
router.register('api/task-templates', TaskTemplateViewSet, base_name='task_template'),
router.register('api/task-templates-custom-fields', CustomFieldViewSet, base_name='task-template-custom-fields'),
router.register('api/workflow-templates', WorkflowTemplateViewSet, base_name='workflow_template'),
router.register('api/project-templates', ProjectTemplateViewSet, base_name='project_template'),
router.register('api/global-custom-fields', GlobalCustomFieldViewSet, base_name='global-custom-fields'),
router.register(
    'api/global-custom-field-values', GlobalCustomFieldValueViewSet, base_name='global-custom-filed-values'
),
router.register(
    'api/workflow-templates-custom-fields',
    WorkflowTemplateCustomFieldViewSet,
    base_name='workflow-template-custom-fields',
),
router.register(
    'api/project-templates-custom-fields',
    ProjectTemplateCustomFieldViewSet,
    base_name='project-template-custom-fields',
),
router.register('api/global_search', GlobalSearchViewSet, base_name='global_search'),
router.register('api/project_rank', ProjectRankViewSet, base_name='project_rank'),
router.register('api/projectrankchange', ProjectRankChangeViewSet, base_name='projectrankchange'),
router.register('api/workflow_rank', WorkflowRankViewSet, base_name='workflow_rank'),
router.register('api/task_rank', TaskRankViewSet, base_name='task_rank'),
router.register('api/tags', TagViewSet, base_name='tags'),
router.register('api/audit_history', AuditHistoryViewSet, base_name='audit_history_list'),
router.register('api/work_group_members', WorkGroupMemberViewSet, base_name='work_group_members_list'),
router.register('api/work_group', WorkGroupViewSet, base_name='work_group_list'),
router.register('api/company_work_group', CompanyWorkGroupViewSet, base_name='company_work_group_list'),
router.register('api/doc_request_portal', ServiceDeskAttachmentViewSet, base_name='doc_request_portal'),
router.register('api/company_service_desk_portal', RequestPortalViewSet, base_name='company_service_desk_portal'),
router.register('api/pending_request_desk', PendingRequestViewSet, base_name='pending_request_desk'),
router.register('api/submitted_request_portal', SubmittedRequestViewSet, base_name='submitted_request_portal'),
router.register(
    'api/submit_new_request_portal', SubmitServiceDeskRequestViewSet, base_name='submit_new_request_portal'
),
router.register('api/user_information', ServiceDeskUserViewSet, base_name='user_information'),
router.register(
    'api/servicedeskrequest_message', ServiceDeskRequestMessageViewSet, base_name='servicedeskrequest_message'
),
router.register('api/user_workgroup', UserWorkGroupViewSet, base_name='user_workgroup'),
router.register('api/privilage_report', PrivilegeReportViewSet, base_name='privilage_report'),
router.register('api/tag_report', TagReportViewSet, base_name='tag_report'),
router.register('api/group_workload_report', GroupWorkLoadReportViewSet, base_name='group_workload_report')
router.register(
    'api/team_member_workload_report', TeamMemberWorkLoadReportViewSet, base_name='team_member_workload_report'
),
router.register('api/efficiency_report', EfficiencyReportViewSet, base_name='efficiency_report'),
router.register('api/productivity_report', ProductivityReportViewSet, base_name='productivity_report'),
router.register('api/workflows_statistic', WorkflowStatisticsViewSet, base_name='task_statistic'),
router.register('api/projects_statistic', ProjectStatisticsViewSet, base_name='task_statistic'),
router.register('api/dashboard_statistic', DashboardStatisticsViewSet, base_name='dashboard_statistic')
router.register('api/document_share', ShareDocumentViewSet, base_name='share_document')
router.register('api/celerytaskdrain', CeleryDrainViewSet, base_name='celerytaskdrain'),
# schema_view = get_params_swagger_view(title='API Docs')

urlpatterns = [
    # url(r'^docs/', schema_view),
    path('task_create_postmark/', PostmarkTaskWebHook.as_view(), name='task-create-postmark'),
    path('project_create_postmark/', PostmarkProjectWebHook.as_view(), name='project-create-postmark'),
    path('project_task_common_create_postmark/', PostmarkCommonWebHook.as_view(), name='common-handle-postmark'),
    path('template-test/', TemplateTestView.as_view(), name='home'),
    path('api/document_copy_move/', AttachmentCopyOrMoveView.as_view(), name='document-copy-move'),
    path(
        'api/resend-requestpage-link/<email>/', ReSendServiceDeskLinkAPIView.as_view(), name='resend-requestpage-link'
    ),
    path(
        'api/servicedesk-varification/<token>/',
        ServiceDeskTokenVerificationAPIView.as_view(),
        name='servicedesk-varification',
    ),
]

urlpatterns += router.urls
