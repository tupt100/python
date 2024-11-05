import copy
import datetime
import json
import os
import socket
import time
import uuid
from datetime import timedelta

import requests
from authentication.models import GroupAndPermission, Organization, User
from authentication.permissions import PermissionManagerPermission
from authentication.utils import get_client_ip
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import IntegrityError, models
from django.db.models import Avg, Count, ExpressionWrapper, F, Prefetch, Q, fields
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_filters import rest_framework as filters
from projects.api.serializers import (
    AttachmentBasicSerializer,
    AttachmentCreateSerializer,
    AttachmentDetailsSerializer,
    AttachmentListSerializer,
    AttachmentUpdateSerializer,
    DocumentBasicSerializer,
    TagBasicSerializer,
    TaskCreateSerializer,
    UserWorkGroupListSerializer,
    WorkflowCreateSerializer,
    WorkflowUpdateSerializer,
    WorkGroupAddMemberSerializer,
    WorkGroupDetailSerializer,
    WorkGroupListSerializer,
    WorkGroupMemberCreateSerializer,
    WorkGroupRemoveMemberSerializer,
    WorkGroupUpdateSerializer,
)
from projects.models import (
    Attachment,
    AuditHistory,
    CompletionLog,
    GroupWorkLoadLog,
    Privilage_Change_Log,
    Project,
    ProjectRank,
    ServiceDeskAttachment,
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskRequestMessage,
    ServiceDeskUserInformation,
    Tag,
    TagChangeLog,
    Task,
    TeamMemberWorkLoadLog,
    Workflow,
    WorkflowRank,
    WorkGroup,
    WorkGroupMember,
    WorkProductivityLog,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action, list_route
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import ListModelMixin
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import (
    AttachmentFilterSet,
    CompanyWorkGroupFilterSet,
    GroupWorkLoadFilterSet,
    PrivilageReportFilterSet,
    ProjectFilterSet,
    TagFilterSet,
    TagReportFilterSet,
    TeamMemberWorkLoadFilterSet,
    WorkflowFilterSet,
    WorkGroupFilterSet,
    WorkProductivityLogFilterSet,
)
from .globalcustomfields.api.views import *  # noqa
from .helpers import (
    AuditHistoryCreate,
    ReformatAuditHistory,
    ServiceDeskRequestAuditHistory,
    archive_project,
    archive_workflow,
    attachment_copy_or_move,
    complete_project,
    complete_workflow,
    completed_request_reply,
    document_associate_history,
    new_internal_message_notification,
    new_request_notification_to_team_member,
    project_attachment_uploaded_notification,
    project_new_message_notification,
    project_notify_user_for_new_message,
    project_send_notification_to_servicedeskuser,
    request_submit_notification,
    resend_link_to_user,
    send_notification_to_servicedeskuser,
    send_notification_to_user,
    share_document_to_user,
    task_attachment_uploaded_notification,
    task_notify_user_for_new_message,
    user_attachment_authorization_permission,
    user_permission_check,
    workflow_attachment_uploaded_notification,
    workflow_new_message_notification,
    workflow_notify_user_for_new_message,
    workflow_send_notification_to_servicedeskuser,
    workgroup_assigned_notification,
)
from .permissions import (
    AttachmentPermission,
    CompanyWorkGroupPermission,
    CustomPermission,
    EfficiencyPermission,
    GroupWorkLoadReportPermission,
    PendingRequestPermission,
    RankPermission,
    RequestPermission,
    ServiceDeskAttachmentPermission,
    ServiceDeskPermission,
    SubmittedRequestPermission,
    TagPermission,
    TagReportPermission,
    TeamMemberWorkLoadPermission,
    UserWorkGroupPermission,
    UserWorkGroupPermissionCustom,
    WorkGoupPermission,
    WorkGroupMemberPermission,
    WorkProductivityLogPermission,
)
from .serializers import (
    AssociateNewRequestSerializer,
    AuditHistorySerializer,
    CompanyWorkGroupBasicSerializer,
    CompletedGroupWorkLoadReportListSerializer,
    CompletedTagReportListSerializer,
    EfficiencyReportFileSerializer,
    EfficiencyReportSerializer,
    GlobalSearchProjectSerializer,
    GlobalSearchTaskSerializer,
    GlobalSearchWorkflowSerializer,
    GroupWorkLoadLogReportSerializer,
    ItemTitleRenameSerializer,
    MessageDeleteSerializer,
    MessageListSerializer,
    MessageSerializer,
    OpenGroupWorkLoadReportListSerializer,
    OpenTagReportListSerializer,
    PendingRequestMessageSerializer,
    PrivielgeSerializer,
    ProductivityReporGraphSerializer,
    ProductivityReportFileSerializer,
    ProductivityReportListSerializer,
    ProductivityReportSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMessageSerializer,
    ProjectRankChangeSerializer,
    ProjectRankDetailSerializer,
    ProjectRankListSerializer,
    ProjectRankSerializer,
    ProjectUpdateSerializer,
    RequestDetailsSerializer,
    RequestListSerializer,
    ServiceDeskAttachmentCreateSerializer,
    ServiceDeskExternalRequestDetailSerializer,
    ServiceDeskExternalRequestListSerializer,
    ServiceDeskListSerializer,
    ServiceDeskRequestCreateSerializer,
    ServiceDeskRequestDocumentUploadSerializer,
    ServiceDeskUserCreateSerializer,
    ShareDocumentSerializer,
    SubmitRequestMessageSerializer,
    TagCountDetailSerializer,
    TagCreateSerializer,
    TagDetailSerializer,
    TagReportSerializer,
    TeamMemberWorkLoadReportFileSerializer,
    TeamMemberWorkLoadReportListSerializer,
    WorkflowDetailSerializer,
    WorkflowMessageSerializer,
    WorkflowRankDetailSerializer,
    WorkflowRankListSerializer,
    WorkflowRankSerializer,
)
from .tasksapp.api.views import *  # noqa
from .templates.api.views import *  # noqa


class ProjectViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all project of my organization

    * API to filter project by status
    ```
    Status values ==> 1: New, 2: In-Progress, 3: Completed, 4: Archived
    To filter project by New > status=1
    To filter project by New & Completed > status=1,3
    ```

    * Filter project by importance
    ```
    Importance values ==> 1: Low, 2: Med, 3: High
    To filter project by High > importance=3
    To filter project by High & Low > importance=1,3
    ```

    * API to filter project by created_at,due_date with date range
    ```
    To filter project by date range:
    > For project created between 20 march to 30 march
      project__created_at_after=2019-03-20&created_at_before=2019-03-30
    > For project due date between 20 march to 30 march
      project__due_date_after=2019-03-20&due_date_before=2019-03-30

    To filter project using text: `today, yesterday, week, month, year`
    > For project created today
      project__created_at_txt=today
    > For project due date today
      project__due_date_txt=today
    ```

    * API to Filter project by owner
    ```
    To filter project by owner > owner=1
    To filter project by owner> owner=1,3
    ```

    * API to Sort project by fields
    ```
    To sort project by any field pass that field name in ordering
    Sorting fields: 'project__importance','project__name', 'project__due_date',
    e.g : ascending by name > ordering=project__name
         descending by name > ordering=-project__name
    ```

    * API to Sort project by rank
    ```
    Sort by rank in ascending order : order_by_rank=rank
    Sort by rank in descending order : order_by_rank=-rank
    ```

    create:
    API to create new project

    * project `name` and `owner`(user id) is required filed.
    * You can set importance level of project `importance`
    * Importance values ==> 1: Low, 2: Med, 3: High
    * `description`: description of project
    * `assigned_to_users` is list of user id
        to add users as team member [1,2,3]
    * `attachments` is list of attachment id [1,3,4]
    * `project_tags` is list of tag ["abc"]

    partial_update:
    API to update Project details you need to pass that project id

    * change due date for a project
    ```
    To update due date pass `due_date` as below example:
        { "due_date": "2029-11-09" } `or`
        { "due_date": "2009-11-09T00:00:00Z" }
    ```

    * change importance level of project
    ```
    To update importance level of project:
        Importance values ==> 1: Low, 2: Med, 3: High
        To set High ==> { "importance": 3 }
    ```

    * change project status
    ```
    To change project status
        Status options ==> 1: Active, 2: Completed, 3: Archive
        To Complete the project ==> { "status": 2 }
    ```

    * add documents in project
    ```
    To add documents in project pass document's ids as below example:
        attachments=[1, 2]
    ```

    * add tags in project
    ```
    To add tags in project pass tag (including old) below example:
        project_tags=["abc","codal"]
    ```
    """

    model = Project
    permission_classes = (CustomPermission,)
    filterset_class = ProjectFilterSet
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter, SearchFilter)
    ordering_fields = ['project__importance', 'project__name', 'project__due_date', 'rank', 'project__owner']
    search_fields = [
        'project__name',
    ]

    def get_queryset(self):
        date_today = datetime.datetime.utcnow().date()
        user = self.request.user
        company = user.company
        group = user.group
        queryset = ProjectRank.objects.select_related('project', 'project__owner').prefetch_related(
            'project__assigned_to_users',
            Prefetch('project__attachments', Attachment.objects.active()),
        )
        if self.action == 'list':
            queryset = queryset.annotate(
                total_task=Count('project__workflow_assigned_project__task_workflow__id'),
                completed_task=Count(
                    'project__workflow_assigned_project__task_workflow__id',
                    filter=models.Q(project__workflow_assigned_project__task_workflow__status__in=[3, 4]),
                ),
                passed_due=Count(
                    'project__workflow_assigned_project__task_workflow__id',
                    filter=models.Q(project__workflow_assigned_project__task_workflow__due_date__date__lt=date_today),
                    exclude=models.Q(project__workflow_assigned_project__task_workflow__status__in=[3, 4]),
                ),
            )
        if company and user_permission_check(user, 'project'):
            queryset = (
                queryset.filter(project__organization=company, user=user)
                .distinct('project_id')
                .order_by('-project_id')
            )
        else:
            queryset = (
                queryset.filter(
                    Q(project__organization=company, user=user),
                    Q(project__owner=user)
                    | Q(project__assigned_to_users=user)
                    | Q(project__created_by=user)
                    | Q(project__assigned_to_group__group_members=user),
                )
                .distinct('project_id')
                .order_by('-project_id')
            )
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(project__status__in=[2, 3])
        user_ids = []
        group_ids = []
        q_user = self.request.query_params.get('user', '')
        if q_user:
            [user_ids.append(int(x)) for x in q_user.split(',')]
        q_group_member = self.request.query_params.get('group_member', '')
        q_group = self.request.query_params.get('group', '')
        if q_group:
            [group_ids.append(int(x)) for x in q_group.split(',')]
        if q_user and q_group_member and not q_group:
            result_queryset = queryset.filter(
                Q(project__assigned_to_users__id__in=user_ids)
                | Q(project__assigned_to_group__group_members__id__in=user_ids)
                | Q(project__owner__id__in=user_ids)
            ).distinct('project_id')
            return result_queryset
        elif q_user and q_group_member and q_group:
            result_queryset = queryset.filter(
                Q(project__assigned_to_users__id__in=user_ids)
                | Q(project__assigned_to_group__group_members__id__in=user_ids)
                | Q(project__assigned_to_group__id__in=group_ids)
                | Q(project__owner__id__in=user_ids)
            ).distinct('project_id')
            return result_queryset
        elif q_group and not (q_user and q_group_member):
            result_queryset = queryset.filter(Q(project__assigned_to_group__id__in=group_ids)).distinct('project_id')
            return result_queryset
        else:
            pass
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return ProjectCreateSerializer
        elif self.action == 'retrieve':
            return ProjectRankDetailSerializer
        elif self.action == 'partial_update':
            return ProjectUpdateSerializer
        elif self.action == 'rename_title':
            return ItemTitleRenameSerializer
        elif self.action == 'request_associate_to_project':
            return AssociateNewRequestSerializer
        elif self.action == 'project_add_messages':
            return ProjectMessageSerializer
        elif self.action == 'project_delete_messages':
            return MessageDeleteSerializer
        return ProjectRankListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).distinct()
        context = self.paginate_queryset(queryset)
        serializer = ProjectRankListSerializer(context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {'detail': 'Project created successfully', 'project_id': instance.id}, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        partial = True
        user = request.user
        company = user.company
        if company and user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        instance = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        if instance.status in [3, '3', 2, '2']:
            return Response(
                {"detail": "You cannot update " "archive/completed project."}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        project_status = request.data.get('status')
        if project_status in [2, '2']:
            # Re-arrange active and completed/archive project rank
            # rearrange_project_rank(instance)
            AuditHistoryCreate("project", instance.id, user, "Marked Completed at")
            # Complete all workflow and task related to this project
            complete_project(instance, request.user)
        elif project_status in [3, '3']:
            AuditHistoryCreate("project", instance.id, request.user, "Archived at")
            # Re-arrange active and completed/archive project rank
            # rearrange_project_rank(instance)
            # Archive all workflow and task related to this project
            archive_project(instance)
        elif project_status in [4, '4']:
            AuditHistoryCreate("project", instance.id, user, "External Request at")
        elif project_status in [5, '5']:
            AuditHistoryCreate("project", instance.id, user, "External Update at")
        else:
            pass
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        return Response(ProjectDetailSerializer(instance, context={'request': request}).data)

    def retrieve(self, request, *args, **kwargs):
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        instance = get_object_or_404(self.get_queryset(), project_id=int(kwargs.get('pk')))
        AuditHistoryCreate("project", instance.project_id, self.request.user, "Viewed By")
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def rename_title(self, request, pk=None):
        """
        Extra action to rename/update title of a Project.

        * to rename title for a project, id need to be passed.
        ```
        To update/rename title pass `name` as below:
        { "name": "updating project title" }
        ```
        """
        user = self.request.user
        company = user.company
        if company and user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [3, '3', 2, '2']:
            return Response(
                {"detail": "You cannot update " "archive/completed project."}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            instance.name = serializer.data['name']
            instance.save()
            # create record in AuditHistory
            AuditHistoryCreate("project", instance.id, request.user, "Renamed by")
            return Response({'detail': 'Project title updated.'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def request_associate_to_project(self, request, pk=None):
        """
        * To Associate Request to project
        ```
        * user_name is required
        * user_email is required
        * description is required(this would be a message)
        * attachments are optional
        ```
        """
        user = request.user
        company = user.company
        if company and user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [2, 3] or ServiceDeskExternalRequest.objects.filter(project=instance).exists():
            return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user_email = serializer.data['user_email'].lower().strip()
            servicedesk_user = ServiceDeskUserInformation.objects.filter(user_email=user_email).first()
            if not servicedesk_user:
                user_name = serializer.data['user_name']
                organization = instance.organization
                access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                expiration_date = timezone.now() + timedelta(7)
                servicedesk_user = ServiceDeskUserInformation.objects.create(
                    user_email=user_email,
                    user_name=user_name,
                    organization=organization,
                    expiration_date=expiration_date,
                    access_token=access_token,
                )
            user_information = servicedesk_user
            subject = instance.name
            request_priority = instance.importance
            description = serializer.data['description']
            request_obj = ServiceDeskRequest.objects.create(
                user_information=user_information,
                subject=subject,
                description=description,
                request_priority=request_priority,
                is_delete=True,
                is_internal_request=True,
            )
            # send notification to NRU for request submitted successfully
            request_submit_notification.delay(request_obj, user, instance, "project")
            external_request_obj = ServiceDeskExternalRequest.objects.create(
                project=instance, servicedeskuser=servicedesk_user, created_by=user, service_desk_request=request_obj
            )
            message_obj = ServiceDeskRequestMessage.objects.create(
                created_by_user=user, project=instance, message=description, is_external_message=True
            )
            if 'attachments' in serializer.data.keys():
                content_type = ContentType.objects.get(app_label='projects', model='project')
                # Document Uploaded to New Project
                attachment_exist = False
                for attachment in serializer.data['attachments']:
                    attachment_obj = Attachment.objects.filter(
                        id=attachment,
                        organization=company,
                        is_delete=False,
                        created_by=user,
                        project=None,
                        workflow=None,
                        task=None,
                        message_document=None,
                    ).first()
                    if attachment_obj:
                        attachment_exist = True
                        attachment_obj.content_type = content_type
                        attachment_obj.object_id = instance.id
                        attachment_obj.message_document = message_obj
                        attachment_obj.save()
                        AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                        document_associate_history(
                            "attachment", attachment_obj.id, instance.name, "Associated Project", request.user
                        )
                if attachment_exist:
                    AuditHistoryCreate("project", instance.id, request.user, "Document Uploaded at")
                    project_attachment_uploaded_notification(instance, instance.owner)
                    if instance.assigned_to_users:
                        for project_user in instance.assigned_to_users.all():
                            if project_user != instance.owner:
                                project_attachment_uploaded_notification(instance, project_user)
                    if instance.assigned_to_group:
                        for projects_group in instance.assigned_to_group.all():
                            [
                                project_attachment_uploaded_notification(instance, group_member)
                                for group_member in projects_group.group_members.all()
                            ]
            # send notification to NRU for "request is picked up"
            project_send_notification_to_servicedeskuser.delay(external_request_obj)
            return Response({'detail': 'Project linked to request ' 'successfully!.'}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def project_add_messages(self, request, *args, **kwargs):
        user = request.user
        company = user.company
        group = user.group
        if company and user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(project__status__in=[2, 3])
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            project_obj = get_object_or_404(queryset, pk=serializer.data['project'])
            external_request_obj = ServiceDeskExternalRequest.objects.filter(project=project_obj).first()
            if serializer.data['is_internal_message']:
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    project=project_obj,
                    created_by_user=user,
                    is_internal_message=True,
                )
                if 'attachments' in serializer.data.keys() and project_obj.status not in [2, 3]:
                    content_type = ContentType.objects.get(app_label='projects', model='project')
                    # Document Uploaded to New Project
                    attachment_exist = False
                    for attachment in serializer.data['attachments']:
                        attachment_obj = Attachment.objects.filter(
                            id=attachment,
                            organization=company,
                            is_delete=False,
                            created_by=user,
                            project=None,
                            workflow=None,
                            task=None,
                            message_document=None,
                        ).first()
                        if attachment_obj:
                            attachment_exist = True
                            attachment_obj.content_type = content_type
                            attachment_obj.object_id = project_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, project_obj.name, "Associated Project", request.user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("project", project_obj.id, user, "Document Uploaded at")
                # send new message notification to assigned user
                new_internal_message_notification.delay(project_obj, "project", message_obj)
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            elif serializer.data['is_external_message'] and external_request_obj:
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    project=project_obj,
                    created_by_user=user,
                    is_external_message=True,
                )
                external_request_obj.replies += 1
                external_request_obj.save()
                # new message notification to service desk user
                project_new_message_notification.delay(message_obj, project_obj, user)
                if 'attachments' in serializer.data.keys() and project_obj.status not in [2, 3]:
                    content_type = ContentType.objects.get(app_label='projects', model='project')
                    # Document Uploaded to New Project
                    attachment_exist = False
                    for attachment in serializer.data['attachments']:
                        attachment_obj = Attachment.objects.filter(
                            id=attachment,
                            organization=company,
                            is_delete=False,
                            created_by=user,
                            project=None,
                            workflow=None,
                            task=None,
                            message_document=None,
                        ).first()
                        if attachment_obj:
                            attachment_exist = True
                            attachment_obj.content_type = content_type
                            attachment_obj.object_id = project_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, project_obj.name, "Associated Project", request.user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("project", project_obj.id, user, "Document Uploaded at")
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response({'detail': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'detail': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'post',
        ],
    )
    def project_delete_messages(self, request, *args, **kwargs):
        """
        * To delete message of workflow pass
            workflow id and message id.
        ```
        > To update/rename title pass `name` as below:
          { "message_id": 10}
        * success message would be "message deleted successfully" and
            status 200
        * invalid request will return "please enter valid data" and
            status 400
        * if message is already deleted then API will return
            "This message is already deleted." and status 400
        ```
        """
        if not str(kwargs.get('pk')).isdigit() or not str(request.data['message_id']).isdigit():
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        project_obj = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            message_obj = ServiceDeskRequestMessage.objects.filter(
                id=serializer.data['message_id'], project=project_obj, is_delete=False, created_by_user=user
            ).first()
            if message_obj:
                message_obj.is_delete = True
                message_obj.save()
                return Response({'detail': 'message deleted successfully.'}, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectRankViewSet(viewsets.ModelViewSet):
    model = Project
    permission_classes = (RankPermission,)
    queryset = ProjectRank.objects.all()

    def get_queryset(self):
        queryset = super(ProjectRankViewSet, self).get_queryset()
        user = self.request.user
        company = user.company
        queryset = queryset.filter(project__organization=company, user=user)
        if self.request.method == 'PATCH' and self.request.data:
            queryset = queryset.filter(project__organization=company, user=user).order_by('-rank')
            return queryset
        return self.queryset.none()

    def get_serializer_class(self):
        if self.request.method in ['PATCH']:
            return ProjectRankSerializer
        return None


class ProjectRankChangeViewSet(viewsets.ModelViewSet):
    model = Project
    permission_classes = (RankPermission,)
    queryset = ProjectRank.objects.all()

    def get_queryset(self):
        queryset = super(ProjectRankChangeViewSet, self).get_queryset()
        user = self.request.user
        company = user.company
        queryset = queryset.filter(project__organization=company, user=user)
        if self.request.method == 'PATCH' and self.request.data:
            queryset = queryset.filter(project__organization=company, user=user).order_by('-rank')
            return queryset
        return self.queryset.none()

    def get_serializer_class(self):
        if self.request.method in ['PATCH']:
            return ProjectRankChangeSerializer
        return None


class WorkflowViewSet(viewsets.ModelViewSet):
    """
    create:
    API to create new workflow

    * workflow `name` and `owner`(user id) is required filed.
    * You can set importance level of workflow `importance`
    * Importance values ==> 1: Low, 2: Med, 3: High
    * `description`: description of workflow
    * `assigned_to_users` is list of user id
        to add users as team member [1,2,3]
    * `attachments` is list of attachment id [1,3,4]
    * `workflow_tags` is list of tag's id [1,2,3]
    list:
    API to list all Workflow

    * API to Sort workflow by rank
    ```
    Sort by rank in ascending order : order_by_rank=rank
    Sort by rank in descending order : order_by_rank=-rank
    ```

    * Sort Workflow by fields
    ```
    To sort workflow by any field pass that field name in ordering
    Sorting fields: 'workflow__importance', 'workflow__name',
                    'workflow__due_date', 'rank'
    e.g : ascending by name > ordering=workflow__name
         descending by name > ordering=-workflow__name
    ```

    * API to filter workflow by status
    ```
    Status values ==> 1: New, 2: Completed, 3: Archived
    To filter workflow by New > status=1
    To filter workflow by New & Completed > status=1,2
    ```

    * API to Filter Workflow by importance
    ```
    Importance values ==> 1: Low, 2: Med, 3: High
    To filter workflow by High > importance=3
    To filter workflow by High & Low > importance=1,3
    ```

    * API to Filter Workflow by owner
    ```
    To filter workflow by owner > owner=1
    To filter workflow by owner> owner=1,3
    ```

    * API to filter workflow by created_at,due_date with date range
    ```
    To filter workflow by date range:
    > For workflow created between 20 march to 30 march
      workflow__created_at_after=2019-03-20&created_at_before=2019-03-30
    > For workflow due date between 20 march to 30 march
      workflow__due_date_after=2019-03-20&due_date_before=2019-03-30

    To filter workflow using text: `today, yesterday, week, month, year`
    > For workflow created today
      workflow__created_at_txt=today
    > For workflow due date today
      workflow__due_date_txt=today
    ```

    partial_update:
    API to update Workflow details you need to pass that workflow id

    * change due date for a workflow
    ```
    To update due date pass `due_date` as below example:
        { "due_date": "2029-11-09" } `or`
        { "due_date": "2009-11-09T00:00:00Z" }
    ```

    * change importance level of workflow
    ```
    To update importance level of workflow:
        Importance values ==> 1: Low, 2: Med, 3: High
        To set High ==> { "importance": 3 }
    ```

    * change work status
    ```
    To change workflow status
        Status options ==> 1: Active, 2: Completed, 3: Archive
        To Complete the workflow ==> { "status": 2 }
    ```

    * add documents in workflow
    ```
    To add documents in workflow pass document's ids as below example:
        attachments=[1, 2]
    ```

    * add tags in workflow
    ```
    To add tags in workflow pass tag's ids as below example:
        workflow_tags=[1,2,3]
    ```
    """

    model = Workflow
    permission_classes = (CustomPermission,)
    filterset_class = WorkflowFilterSet
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter, SearchFilter)
    ordering_fields = ['workflow__importance', 'workflow__name', 'workflow__due_date', 'rank', 'workflow__owner']
    search_fields = ['workflow__name']

    def get_queryset(self):
        queryset = WorkflowRank.objects.none()
        user = self.request.user
        company = user.company
        group = user.group
        if company:
            if user_permission_check(user, 'workflow'):
                queryset = (
                    WorkflowRank.objects.filter(workflow__organization=company, user=user)
                    .distinct('workflow_id')
                    .order_by('-workflow_id')
                )
            else:
                queryset = (
                    WorkflowRank.objects.filter(
                        Q(workflow__organization=company, user=user),
                        Q(workflow__owner=user)
                        | Q(workflow__assigned_to_users=user)
                        | Q(workflow__created_by=user)
                        | Q(workflow__assigned_to_group__group_members=user),
                    )
                    .distinct('workflow_id')
                    .order_by('-workflow_id')
                )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True,
            ).exists():
                queryset = queryset.exclude(workflow__status__in=[2, 3])
            user_ids = []
            group_ids = []
            q_user = self.request.query_params.get('user', '')
            if q_user:
                [user_ids.append(int(x)) for x in q_user.split(',')]
            q_group_member = self.request.query_params.get('group_member', '')
            q_group = self.request.query_params.get('group', '')
            if q_group:
                [group_ids.append(int(x)) for x in q_group.split(',')]
            if q_user and q_group_member and not q_group:
                result_queryset = queryset.filter(
                    Q(workflow__assigned_to_users__id__in=user_ids)
                    | Q(workflow__assigned_to_group__group_members__id__in=user_ids)
                    | Q(workflow__owner__id__in=user_ids)
                ).distinct('workflow_id')
                return result_queryset
            elif q_user and q_group_member and q_group:
                result_queryset = queryset.filter(
                    Q(workflow__assigned_to_users__id__in=user_ids)
                    | Q(workflow__assigned_to_group__group_members__id__in=user_ids)
                    | Q(workflow__assigned_to_group__id__in=group_ids)
                    | Q(workflow__owner__id__in=user_ids)
                ).distinct('workflow_id')
                return result_queryset
            elif q_group and not (q_user and q_group_member):
                result_queryset = queryset.filter(Q(workflow__assigned_to_group__id__in=group_ids)).distinct(
                    'workflow_id'
                )
                return result_queryset
            else:
                pass
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkflowCreateSerializer
        elif self.action == 'retrieve':
            return WorkflowRankDetailSerializer
        elif self.action == 'partial_update':
            return WorkflowUpdateSerializer
        elif self.action == 'rename_title':
            return ItemTitleRenameSerializer
        elif self.action == 'request_associate_to_workflow':
            return AssociateNewRequestSerializer
        elif self.action == 'workflow_add_messages':
            return WorkflowMessageSerializer
        elif self.action == 'workflow_delete_messages':
            return MessageDeleteSerializer
        return WorkflowRankListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = WorkflowRankListSerializer(context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {'detail': 'Workflow created successfully', 'workflow_id': instance.id}, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        user = request.user
        company = user.company
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(assigned_to_users=user)
                | Q(owner=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        instance = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        if instance.status in [3, '3', 2, '2']:
            return Response(
                {"detail": "You cannot update " "archive/completed workflow."}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        workflow_status = request.data.get('status')
        if workflow_status in [2, '2']:
            # Re-arrange active and completed/archive workflow rank
            # rearrange_workflow_rank(instance)
            # Complete all task related to this workflow
            AuditHistoryCreate("workflow", instance.id, request.user, "Marked Completed at")
            complete_workflow(instance, request.user)
        elif workflow_status in [3, '3']:
            AuditHistoryCreate("workflow", instance.id, request.user, "Archived at")
            # re-arrange active and completed/archive workflow rank
            # rearrange_workflow_rank(instance)
            # Archive all task related to this workflow
            archive_workflow(instance)
        elif workflow_status in [4, '4']:
            AuditHistoryCreate("workflow", instance.id, user, "External Request at")
        elif workflow_status in [5, '5']:
            AuditHistoryCreate("workflow", instance.id, user, "External Update at")
        else:
            pass
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        return Response(WorkflowDetailSerializer(instance, context={'request': request}).data)

    def retrieve(self, request, *args, **kwargs):
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        instance = get_object_or_404(self.get_queryset(), workflow_id=int(kwargs.get('pk')))
        AuditHistoryCreate("workflow", instance.workflow_id, request.user, "Viewed By")
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def rename_title(self, request, pk=None):
        """
        Extra action to rename/update title of a Workflow.

        * to rename title for a workflow, workflow-Id need to be passed.

        ```
        To update/rename title pass `name` as below:
        { "name": "updating workflow title" }
        ```
        """
        user = self.request.user
        company = user.company
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [3, '3', 2, '2']:
            return Response(
                {"detail": "You cannot update " "archive/completed project."}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            instance.name = serializer.data['name']
            instance.save()
            # Enter record in AuditHistory table
            AuditHistoryCreate("workflow", instance.id, self.request.user, "Renamed by")
            return Response({'detail': 'Workflow title updated.'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def request_associate_to_workflow(self, request, pk=None):
        """
        * To Associate Request to task
        ```
        * user_name is required
        * user_email is required
        * description is required(this would be a message)
        * attachments are optional
        ```
        """
        if not str(request.data['user_email']) or not str(request.data['user_email']):
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [2, 3] or ServiceDeskExternalRequest.objects.filter(workflow=instance).exists():
            return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user_email = serializer.data['user_email'].lower().strip()
            servicedesk_user = ServiceDeskUserInformation.objects.filter(user_email=user_email).first()
            if not servicedesk_user:
                user_name = serializer.data['user_name']
                organization = instance.organization
                access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                expiration_date = timezone.now() + timedelta(7)
                servicedesk_user = ServiceDeskUserInformation.objects.create(
                    user_email=user_email,
                    user_name=user_name,
                    organization=organization,
                    expiration_date=expiration_date,
                    access_token=access_token,
                )
            user_information = servicedesk_user
            subject = instance.name
            request_priority = instance.importance
            description = serializer.data['description']
            request_obj = ServiceDeskRequest.objects.create(
                user_information=user_information,
                subject=subject,
                description=description,
                request_priority=request_priority,
                is_delete=True,
                is_internal_request=True,
            )
            # send notification to NRU for request submitted successfully
            request_submit_notification.delay(request_obj, user, instance, "workflow")
            external_request_obj = ServiceDeskExternalRequest.objects.create(
                workflow=instance, servicedeskuser=servicedesk_user, created_by=user, service_desk_request=request_obj
            )
            message_obj = ServiceDeskRequestMessage.objects.create(
                created_by_user=user, workflow=instance, message=description, is_external_message=True
            )
            if 'attachments' in serializer.data.keys():
                content_type = ContentType.objects.get(app_label='projects', model='workflow')
                # Document Uploaded to Workflow
                attachment_exist = False
                for attachment in serializer.data['attachments']:
                    attachment_obj = Attachment.objects.filter(
                        id=attachment,
                        organization=company,
                        is_delete=False,
                        created_by=user,
                        project=None,
                        workflow=None,
                        task=None,
                        message_document=None,
                    ).first()
                    if attachment_obj:
                        attachment_exist = True
                        attachment_obj.content_type = content_type
                        attachment_obj.object_id = instance.id
                        attachment_obj.message_document = message_obj
                        attachment_obj.save()
                        AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                        document_associate_history(
                            "attachment", attachment_obj.id, instance.name, "Associated Workflow", user
                        )
                if attachment_exist:
                    AuditHistoryCreate("workflow", instance.id, user, "Document Uploaded at")
                    workflow_attachment_uploaded_notification(instance, instance.owner)
                    if instance.assigned_to_users:
                        for workflow_user in instance.assigned_to_users.all():
                            if workflow_user != instance.owner:
                                workflow_attachment_uploaded_notification(instance, workflow_user)
                    if instance.assigned_to_group:
                        for workflow_group in instance.assigned_to_group.all():
                            [
                                workflow_attachment_uploaded_notification(instance, group_member)
                                for group_member in workflow_group.group_members.all()
                            ]
            workflow_send_notification_to_servicedeskuser.delay(external_request_obj)
            return Response({'detail': 'Workflow linked to ' 'request successfully!.'}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'get',
        ],
    )
    def workflow_details_statistic(self, request, pk, *args, **kwargs):
        """
        > API will return following detail for selected workflow
        * total number of task as *all_task*
        * total number of completed task as *completed_task*
        * total number of task which has low importance as *low*
        * total number of task which has mid importance as *mid*
        * total number of task which has high importance as *high*
        ```
        """
        user = self.request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'workflow'):

            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        workflow_obj = get_object_or_404(queryset, pk=pk)
        task_queryset = Task.objects.filter(workflow=workflow_obj)
        # check if user has view all permission
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all',
        ).exists():
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view',
        ).exists():
            task_queryset = task_queryset.filter(
                Q(organization=user.company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
        else:
            context = {
                'low': 0,
                'med': 0,
                'high': 0,
                'all_task': 0,
                'completed_task': 0,
            }
            return Response(context, status=status.HTTP_200_OK)
        accessible_task_qset = Task.objects.filter(
            pk__in=task_queryset.values_list('id', flat=True).distinct(), organization=company
        )
        low = accessible_task_qset.filter(importance=1).exclude(status__in=[3, 4]).count()
        med = accessible_task_qset.filter(importance=2).exclude(status__in=[3, 4]).count()
        high = accessible_task_qset.filter(importance=3).exclude(status__in=[3, 4]).count()
        all_task = accessible_task_qset.count()
        comp_task = accessible_task_qset.filter(status__in=[3, 4]).count()
        context = {
            'low': low,
            'med': med,
            'high': high,
            'all_task': all_task,
            'completed_task': comp_task,
        }
        return Response(context, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def workflow_add_messages(self, request, *args, **kwargs):
        user = request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            workflow_obj = get_object_or_404(queryset, pk=serializer.data['workflow'])
            external_request_obj = ServiceDeskExternalRequest.objects.filter(workflow=workflow_obj).first()
            if serializer.data['is_internal_message']:
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    workflow=workflow_obj,
                    created_by_user=user,
                    is_internal_message=True,
                )
                if 'attachments' in serializer.data.keys() and workflow_obj.status not in [2, 3]:
                    content_type = ContentType.objects.get(app_label='projects', model='workflow')
                    # Document Uploaded to Workflow
                    attachment_exist = False
                    for attachment in serializer.data['attachments']:
                        attachment_obj = Attachment.objects.filter(
                            id=attachment,
                            organization=company,
                            is_delete=False,
                            created_by=user,
                            project=None,
                            workflow=None,
                            task=None,
                            message_document=None,
                        ).first()
                        if attachment_obj:
                            attachment_exist = True
                            attachment_obj.content_type = content_type
                            attachment_obj.object_id = workflow_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, workflow_obj.name, "Associated Workflow", user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("workflow", workflow_obj.id, user, "Document Uploaded at")
                # send new message notification to assigned user
                new_internal_message_notification.delay(workflow_obj, "workflow", message_obj)
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            elif external_request_obj and serializer.data['is_external_message']:
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    workflow=workflow_obj,
                    created_by_user=user,
                    is_external_message=True,
                )
                external_request_obj.replies += 1
                external_request_obj.save()
                # new message notification to service desk user
                workflow_new_message_notification.delay(message_obj, workflow_obj, user)
                if 'attachments' in serializer.data.keys() and workflow_obj.status not in [2, 3]:
                    content_type = ContentType.objects.get(app_label='projects', model='workflow')
                    # Document Uploaded to Workflow
                    attachment_exist = False
                    for attachment in serializer.data['attachments']:
                        attachment_obj = Attachment.objects.filter(
                            id=attachment,
                            organization=company,
                            is_delete=False,
                            created_by=user,
                            project=None,
                            workflow=None,
                            task=None,
                            message_document=None,
                        ).first()
                        if attachment_obj:
                            attachment_exist = True
                            attachment_obj.content_type = content_type
                            attachment_obj.object_id = workflow_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, workflow_obj.name, "Associated Workflow", user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("workflow", workflow_obj.id, user, "Document Uploaded at")
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response({'detail': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'post',
        ],
    )
    def workflow_delete_messages(self, request, *args, **kwargs):
        """
        * To delete message of workflow pass workflow id and
          message id.
        ```
        > To update/rename title pass `name` as below:
          { "message_id": 10}
        * success message would be "message deleted successfully" and
            status 200
        * invalid request will return "please enter valid data" and
            status 400
        * if message is already deleted then API will return
            "This message is already deleted." and status 400
        ```
        """
        if not str(kwargs.get('pk')).isdigit() or not str(request.data['message_id']).isdigit():
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        workflow_obj = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            message_obj = ServiceDeskRequestMessage.objects.filter(
                id=serializer.data['message_id'], workflow=workflow_obj, is_delete=False, created_by_user=user
            ).first()
            if message_obj:
                message_obj.is_delete = True
                message_obj.save()
                return Response({'detail': 'message deleted ' 'successfully.'}, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'This message is already' ' deleted.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'get',
        ],
    )
    def workflow_project_statistic(self, request, pk, *args, **kwargs):
        """
        * API to get workflows inside the project
        ```
        > API will return following detail for selected workflow
        > if workflow is associate with project then it will return
        project name with total number of workflow
        > if workflow is not associate with any project then return
          empty dictionary
        > eg:- {
              "project": {
                "id": 01,
                "name": "codal",
                "associated_workflows": 999
              }
            }
        ```
        """
        user = self.request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        workflow_obj = get_object_or_404(queryset, pk=pk)
        if not workflow_obj.project:
            context = {
                'project': {
                    'id': 0,
                    'name': None,
                    'associated_workflows': 0,
                }
            }
            return Response(context, status=status.HTTP_200_OK)
        project_qset = Project.objects.none()
        if GroupAndPermission.objects.filter(
            group=self.request.user.group,
            company=company,
            permission__permission_category='project',
            has_permission=True,
            permission__slug='project_project-view-all',
        ).exists():
            project_qset = Project.objects.filter(organization=company).values_list('id', flat=True)
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            has_permission=True,
            permission__slug='project_project-view',
        ).exists():
            project_qset = (
                Project.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
                .values_list('id', flat=True)
                .distinct('id')
            )
        else:
            pass
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            project_qset = project_qset.exclude(status__in=[2, 3])
        if project_qset.filter(id=workflow_obj.project.id).exists():
            context = {
                'project': {
                    'id': workflow_obj.project.id,
                    'name': workflow_obj.project.name,
                    'associated_workflows': queryset.filter(project_id=workflow_obj.project.id).count(),
                }
            }
            return Response(context, status=status.HTTP_200_OK)
        context = {
            'project': {
                'id': 0,
                'name': None,
                'associated_workflows': 0,
            }
        }
        return Response(context, status=status.HTTP_200_OK)


class WorkflowRankViewSet(viewsets.ModelViewSet):
    model = Workflow
    permission_classes = (RankPermission,)
    queryset = WorkflowRank.objects.all()

    def get_queryset(self):
        queryset = super(WorkflowRankViewSet, self).get_queryset()
        user = self.request.user
        company = user.company
        queryset = queryset.filter(workflow__organization=company, user=user)
        if self.request.method == 'PATCH' and self.request.data:
            queryset = queryset.filter(workflow__organization=company, user=user).order_by('-rank')
            return queryset
        return self.queryset.none()

    def get_serializer_class(self):
        if self.request.method in ['PATCH']:
            return WorkflowRankSerializer
        return None


class WorkflowStatisticsViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    * API to get type wise importance of workflow which is assigned to user
    ```
    > API will return following detail
    * total number of workflow as *total_workflow*
    * total number of task as *total_task*
    * total number of completed task as *completed_task*
    * total number of task which has low importance as *low*
    * total number of task which has mid importance as *mid*
    * total number of task which has high importance as *high*
    * total number of task which has due date today as *due_today*
    * total number of task which has passed due date today as *total_due*
    ```
    """

    permission_classes = (
        IsAuthenticated,
        UserWorkGroupPermission,
    )

    def get_queryset(self):
        user = self.request.user
        group = user.group
        company = user.company
        queryset = Workflow.objects.none()
        if company and user_permission_check(user, 'workflow'):
            queryset = Workflow.objects.filter(organization=company)
        else:
            queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        return queryset

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        user = self.request.user
        company = user.company
        group = user.group
        queryset = self.filter_queryset(self.get_queryset())
        # find total number of workflow based on permission
        total_workflow = queryset.count()
        # total number of task under workflows
        total_task = Task.objects.filter(
            organization=company, workflow_id__in=queryset.values_list('id', flat=True)[::1]
        ).values_list('id', flat=True)[::1]
        if not total_task:
            response = {
                'total_workflow': total_workflow,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        # total number of task under workflow based on my permission
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all',
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            task_queryset = Task.objects.filter(q_obj).distinct('id').values_list('id', flat=True)
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
            task_ids = task_queryset[::1]
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view',
        ).exists():
            task_queryset = (
                Task.objects.filter(
                    Q(organization=user.company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                )
                .distinct('id')
                .values_list('id', flat=True)
            )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
            task_ids = task_queryset[::1]
        else:
            task_ids = []
        if not task_ids:
            response = {
                'total_workflow': total_workflow,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        # to get total task that user has permission to vew
        accessible_task_ids = list(set(total_task).intersection(set(task_ids)))
        if not accessible_task_ids:
            response = {
                'total_workflow': total_workflow,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        accessible_task_qset = Task.objects.filter(pk__in=accessible_task_ids, organization=company).values_list(
            'id', flat=True
        )
        active_accessible_task_qset = accessible_task_qset.exclude(status__in=[3, 4])
        date_today = datetime.datetime.utcnow().date()
        response = {
            'total_workflow': total_workflow,
            'total_task': accessible_task_qset.count(),
            'completed_task': accessible_task_qset.filter(status__in=[3, 4]).count() or 0,
            'low': active_accessible_task_qset.filter(importance=1).count() or 0,
            'mid': active_accessible_task_qset.filter(importance=2).count() or 0,
            'high': active_accessible_task_qset.filter(importance=3).count() or 0,
            'due_today': active_accessible_task_qset.filter(due_date__date=date_today).count() or 0,
            'total_due': active_accessible_task_qset.filter(due_date__date__lt=date_today).count() or 0,
        }
        return Response(dict(response))


class ProjectStatisticsViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    * API to get type wise importance of project which is assigned to user
    ```
    > API will return following details from project
    * total number of project as *total_project*
    * total number of workflow as *total_workflow*
    * total number of task as *total_task*
    * total number of completed task as *completed_task*
    * total number of task which has low importance as *low*
    * total number of task which has mid importance as *mid*
    * total number of task which has high importance as *high*
    * total number of task which has due date today as *due_today*
    * total number of task which has passed due date today as *total_due*
    ```
    """

    permission_classes = (
        IsAuthenticated,
        UserWorkGroupPermission,
    )

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group = user.group
        queryset = Project.objects.none()
        if company and user_permission_check(user, 'project'):
            queryset = Project.objects.filter(organization=company)
        else:
            queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[2, 3])
        return queryset

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        user = self.request.user
        company = user.company
        group = user.group
        queryset = self.filter_queryset(self.get_queryset())
        # find total number of project based on permission
        total_project = queryset.count()
        # total number of workflow under that project
        total_workflow_ids = Workflow.objects.filter(
            project_id__in=queryset.values_list('id', flat=True)[::1], organization=company
        ).values_list('id', flat=True)[::1]
        if not total_workflow_ids:
            response = {
                'total_project': total_project,
                'total_workflow': 0,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        # find total number of workflow's that user has access of
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            has_permission=True,
            permission__slug='workflow_workflow-view-all',
        ).exists():
            workflow_queryset = Workflow.objects.filter(organization=company).values_list('id', flat=True)
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True,
            ).exists():
                workflow_queryset = workflow_queryset.exclude(status__in=[2, 3])
            workflow_ids = workflow_queryset[::1]
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            has_permission=True,
            permission__slug='workflow_workflow-view',
        ).exists():
            workflow_queryset = (
                Workflow.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
                .distinct('id')
                .values_list('id', flat=True)
            )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True,
            ).exists():
                workflow_queryset = workflow_queryset.exclude(status__in=[2, 3])
            workflow_ids = workflow_queryset[::1]
        else:
            workflow_ids = []
        if not workflow_ids:
            response = {
                'total_project': total_project,
                'total_workflow': 0,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        # to get total workflow that user has permission to vew
        accessible_workflow_ids = list(set(total_workflow_ids).intersection(set(workflow_ids)))
        if not accessible_workflow_ids:
            response = {
                'total_project': total_project,
                'total_workflow': 0,
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        total_tasks_ids = Task.objects.filter(
            workflow_id__in=accessible_workflow_ids, organization=company
        ).values_list('id', flat=True)[::1]
        if not total_tasks_ids:
            response = {
                'total_project': total_project,
                'total_workflow': len(accessible_workflow_ids),
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }
            return Response(dict(response))
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all',
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            task_queryset = Task.objects.filter(q_obj).distinct('id')
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
            task_ids = task_queryset[::1]
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view',
        ).exists():
            task_queryset = (
                Task.objects.filter(
                    Q(organization=user.company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                )
                .distinct('id')
                .values_list('id', flat=True)
            )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
            task_ids = task_queryset[::1]
        else:
            task_ids = []
        if not task_ids:
            if not total_tasks_ids:
                response = {
                    'total_project': total_project,
                    'total_workflow': len(accessible_workflow_ids),
                    'total_task': 0,
                    'completed_task': 0,
                    'low': 0,
                    'mid': 0,
                    'high': 0,
                    'due_today': 0,
                    'total_due': 0,
                }
                return Response(dict(response))
        # to get total task that user has permission to vew
        accessible_task_ids = list(set(total_tasks_ids).intersection(set(task_ids)))
        if not accessible_task_ids:
            response = {
                'total_project': total_project,
                'total_workflow': len(accessible_workflow_ids),
                'total_task': 0,
                'completed_task': 0,
                'low': 0,
                'mid': 0,
                'high': 0,
                'due_today': 0,
                'total_due': 0,
            }

            return Response(dict(response))
        accessible_task_qset = Task.objects.filter(pk__in=accessible_task_ids, organization=company).values_list(
            'id', flat=True
        )
        active_accessible_task_qset = accessible_task_qset.exclude(status__in=[3, 4])
        date_today = datetime.datetime.utcnow().date()
        response = {
            'total_project': total_project,
            'total_workflow': len(accessible_workflow_ids),
            'total_task': accessible_task_qset.count(),
            'completed_task': accessible_task_qset.filter(status__in=[3, 4]).count() or 0,
            'low': active_accessible_task_qset.filter(importance=1).count() or 0,
            'mid': active_accessible_task_qset.filter(importance=2).count() or 0,
            'high': active_accessible_task_qset.filter(importance=3).count() or 0,
            'due_today': active_accessible_task_qset.filter(due_date__date=date_today).count() or 0,
            'total_due': active_accessible_task_qset.filter(due_date__date__lt=date_today).count() or 0,
        }
        return Response(dict(response))


class GlobalSearchViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    API to search from all model

    * search API
    ```
    call this API :- projects/api/global_search/?search=search_data
    (any one parameter is required either search or tags)
    pass text that you want to search from entire database
    it will get you list where "codal" exist from
        entire database as a group by separate tables
    ```


    > * Filter sort by
    ```
    Note : By default it will return new to old
    sort_by values ==> 1: A-Z, 2: Z-A
    To filter sort by A-Z > sort_by=1
    ```

    * Filter Status
    ```
    Note : if you didn't pass any value it will take as a all
    Status values ==> 1: New, 2: In Progress, 3: Completed, 5: All
    To filter status by Completed > status=1
    To filter status by New & Completed > status=1,3
    ```

    * Filter Type
    ```
    Note : if you didn't pass any value it will take as a all
    Type values ==> 1: Projects, 2: Workflows, 3: Tasks,
                    4: Documents, 5: All
    To filter Type by Projects > model_type=1
    To filter Type by Projects & Tasks > model_type=1,3
    ```

    * Filter Importance
    ```
    Note : if you didn't pass any value it will take as a all
    Importance values ==> 1: Low, 2: Med, 3: High 4: All
    To filter task by High > importance=3
    To filter task by High & Low > importance=1,3
    ```

    * Filter tags
    ```
    Tags Value ==> you need to use tag get API (/projects/api/tags/)
    when you try filter pass tag id
    To filter single Tags > tags=1
    To filter multiple Tags > tags=2,3
    ```
    """

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        model_list = self.request.query_params.get('model_type', [])
        if model_list:
            model_list = model_list.split(',')
        else:
            model_list.append('5')
        # -------------search start-----------------------#
        tags = self.request.query_params.get('tags', [])
        if tags:
            tags = tags.split(',')
        search = self.request.GET.get('search')
        # check if archive components need to be included in response.
        if not search and not tags:
            return Response({'detail': "search is required field"}, status=status.HTTP_400_BAD_REQUEST)
        # define usable variable
        user = request.user
        company = request.user.company
        group = request.user.group
        # make empty queryset
        docs_qset = Q()
        # make default queryset for search
        if search:
            q_project_filter = Q(name__icontains=search) | Q(project_tags__tag__icontains=search)
            q_workflow_filter = Q(name__icontains=search) | Q(workflow_tags__tag__icontains=search)
            q_task_filter = Q(name__icontains=search) | Q(task_tags__tag__icontains=search)
            q_document_filter = Q(document_tags__tag__icontains=search) | Q(document_name__icontains=search)
        else:
            q_project_filter = Q()
            q_workflow_filter = Q()
            q_task_filter = Q()
            q_document_filter = Q()
        # get all projects based on user permission
        if '1' in model_list or '5' in model_list:
            if GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='project_project-view-all'
            ).exists():
                project_qset = Project.objects.filter(organization=company)
            elif GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='project_project-view'
            ).exists():
                project_qset = Project.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
            else:
                project_qset = Project.objects.none()
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='project',
                permission__slug='project_view-archived',
                has_permission=True,
            ).exists():
                project_qset = project_qset.exclude(status__in=[2, 3])
            if search:
                project_qset = project_qset.filter(q_project_filter)
        else:
            project_qset = Project.objects.none()
        # get all workflows based on user permission
        if '2' in model_list or '5' in model_list:
            if GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view-all'
            ).exists():
                workflow_qset = Workflow.objects.filter(organization=company)
            elif GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view'
            ).exists():
                workflow_qset = Workflow.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
            else:
                workflow_qset = Workflow.objects.none()
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True,
            ).exists():
                workflow_qset = workflow_qset.exclude(status__in=[2, 3])
            if search:
                workflow_qset = workflow_qset.filter(q_workflow_filter)
        else:
            workflow_qset = Workflow.objects.none()
        # get all task based on user permission
        if '3' in model_list or '5' in model_list:
            if GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='task_task-view-all'
            ).exists():
                q_obj = Q()
                q_obj.add(
                    Q(is_private=True, organization=company)
                    & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                    Q.OR,
                )
                q_obj.add(Q(is_private=False, organization=company), Q.OR)
                task_qset = Task.objects.filter(q_obj).distinct('id')
            elif GroupAndPermission.objects.filter(
                group=group, company=company, has_permission=True, permission__slug='task_task-view'
            ).exists():
                task_qset = Task.objects.filter(
                    Q(organization=user.company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                )
            else:
                task_qset = Task.objects.none()
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_qset = task_qset.exclude(status__in=[3, 4])
            if search:
                task_qset = task_qset.filter(q_task_filter)
        else:
            task_qset = Task.objects.none()
        # -------------search completed-----------------------#
        # --------------- filter start ----------------------#
        importance = self.request.query_params.get('importance', [])
        if importance:
            importance = importance.split(',')
        else:
            importance.append(4)
        importance = [int(i) for i in importance]
        f_status = self.request.query_params.get('status', [])
        if f_status:
            f_status = f_status.split(',')
        else:
            f_status.append(5)
        f_status = [int(i) for i in f_status]
        if 3 in f_status:
            f_status.append(4)
        # manage project and workflow status seprate
        pw_status = copy.copy(f_status)
        if 1 and 2 in pw_status:
            pw_status.remove(2)
        elif 2 in pw_status:
            pw_status.remove(2)
            pw_status.append(1)
        for n, i in enumerate(pw_status):
            if i == 4:
                pw_status[n] = 2
        sort_by = self.request.query_params.get('sort_by', 0)
        sort_by = int(sort_by)
        # get all projects based on user permission
        if ('1' in model_list or '5' in model_list) and project_qset:
            # filter with importance
            if 4 not in importance:
                project_qset = project_qset.filter(importance__in=importance)
            # filter with tags
            if tags:
                project_qset = project_qset.filter(project_tags__id__in=tags)
            # status
            if 5 not in pw_status:
                project_qset = project_qset.filter(status__in=pw_status)
            docs_qset.add(Q(project_id__in=project_qset.values_list('id', flat=True).distinct('id')), Q.OR)
            # sort by
            if sort_by == 1:
                project_qset = project_qset.distinct().order_by('name')
            elif sort_by == 2:
                project_qset = project_qset.distinct().order_by('-name')
            else:
                project_qset = project_qset.distinct().order_by('-pk')
        # get all workflows based on user permission
        if ('2' in model_list or '5' in model_list) and workflow_qset:
            # filter with importance
            if 4 not in importance:
                workflow_qset = workflow_qset.filter(importance__in=importance)
            # filter with tags
            if tags:
                workflow_qset = workflow_qset.filter(workflow_tags__id__in=tags)
            # status
            if 5 not in pw_status:
                workflow_qset = workflow_qset.filter(status__in=pw_status)
            docs_qset.add(Q(workflow_id__in=workflow_qset.values_list('id', flat=True).distinct('id')), Q.OR)
            # sort by
            if sort_by == 1:
                workflow_qset = workflow_qset.distinct().order_by('name')
            elif sort_by == 2:
                workflow_qset = workflow_qset.distinct().order_by('-name')
            else:
                workflow_qset = workflow_qset.distinct().order_by('-pk')
        # get all task based on user permission
        if ('3' in model_list or '5' in model_list) and task_qset:
            # filter with importance
            if 4 not in importance:
                task_qset = task_qset.filter(importance__in=importance)
            # filter with tags
            if tags:
                task_qset = task_qset.filter(task_tags__id__in=tags)
            # status
            if 5 not in f_status:
                task_qset = task_qset.filter(status__in=f_status)
            docs_qset.add(Q(task_id__in=list(task_qset.values_list('id', flat=True).distinct('id'))), Q.OR)
            # sort by
            if sort_by == 1:
                task_qset = task_qset.distinct().order_by('name')
            elif sort_by == 2:
                task_qset = task_qset.distinct().order_by('-name')
            else:
                task_qset = task_qset.distinct().order_by('-pk')
        # check document related active project, task and workflow
        # check document related active project, task and workflow
        if '4' in model_list or '5' in model_list:
            document_qset = Attachment.objects.filter(organization=company, is_delete=False)
            if q_document_filter:
                document_qset = document_qset.filter(q_document_filter)
            if docs_qset:
                document_qset = document_qset.filter(docs_qset)  # .filter(attach_qset).distinct('id')
        else:
            document_qset = None
        if ('4' in model_list or '5' in model_list) and document_qset:
            # filter with importance
            if 4 not in importance:
                document_qset = document_qset.filter(
                    Q(project__importance__in=importance)
                    | Q(workflow__importance__in=importance)
                    | Q(task__importance__in=importance)
                )
            # sort by
            if sort_by == 1:
                document_qset = document_qset.distinct().order_by('document_name')
            elif sort_by == 2:
                document_qset = document_qset.distinct().order_by('-document_name')
            else:
                document_qset = document_qset.distinct().order_by('-pk')

        response = {
            'project': GlobalSearchProjectSerializer(
                project_qset, many=True, context={'request': request, 'task_qset': task_qset}
            ).data,
            'workflow': GlobalSearchWorkflowSerializer(
                workflow_qset, many=True, context={'request': request, 'task_qset': task_qset}
            ).data,
            'task': GlobalSearchTaskSerializer(task_qset, many=True, context={'request': request}).data,
            'document': AttachmentListSerializer(document_qset, many=True, context={'request': request}).data,
        }
        return Response(dict(response))


class AttachmentViewSet(viewsets.ModelViewSet):
    """
    list:
    API to filter documents by one or multiple project
    If you want to use this document you have to use `document_url`

    * Filter attachment by project
    ```
    call this API :- projects/api/documents/?projects={project_id1,project_id2}
    pass project id as a comma separated list or single id
    ex:- projects/api/documents/?projects=4,5
        or
        projects/api/documents/?projects=4

    ```

    create:
    API to create documents
    You can at least send `external_url` or `document` and it's necessary send `document_name`
    If you want to use this document you have to use `document_url`
    """

    model = Attachment
    filterset_class = AttachmentFilterSet
    filter_backends = (
        filters.DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )
    search_fields = ['document', 'document_name']
    ordering_fields = ['created_at', 'document', 'document_name', 'created_by']
    parser_classes = (FormParser, MultiPartParser, JSONParser)
    serializer_class = AttachmentCreateSerializer
    permission_classes = (
        IsAuthenticated,
        AttachmentPermission,
    )

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = Attachment.objects.none()
        if company:
            queryset = Attachment.objects.filter(organization=company, is_delete=False)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return AttachmentCreateSerializer
        if self.action == 'list':
            return AttachmentListSerializer
        if self.action == 'partial_update':
            return AttachmentUpdateSerializer
        if self.action == 'rename':
            return AttachmentUpdateSerializer
        if self.action == 'retrieve':
            return AttachmentDetailsSerializer
        return AttachmentListSerializer

    def list(self, request, *args, **kwargs):
        user = request.user
        group = user.group
        company = user.company
        docs_qset = Q()
        t_qset = Task.objects.none()
        w_qset = Workflow.objects.none()
        p_qset = Project.objects.none()
        # check user permission for task
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='task_task-view-all'
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            t_qset = Task.objects.filter(q_obj).distinct('id')
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='task_task-view'
        ).exists():
            t_qset = Task.objects.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        else:
            pass
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            t_qset = t_qset.exclude(status__in=[3, 4])
        # check user permission workflow
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view-all'
        ).exists():
            w_qset = Workflow.objects.filter(organization=company)
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view'
        ).exists():
            w_qset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        else:
            pass
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            w_qset = w_qset.exclude(status__in=[2, 3])
        # check user permission for project
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='project_project-view-all'
        ).exists():
            p_qset = Project.objects.filter(organization=company)
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='project_project-view'
        ).exists():
            p_qset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        else:
            pass
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            p_qset = p_qset.exclude(status__in=[2, 3])
        docs_qset.add(Q(task_id__in=t_qset.values_list('id', flat=True)[::1]), Q.OR)
        docs_qset.add(Q(workflow_id__in=w_qset.values_list('id', flat=True)[::1]), Q.OR)
        docs_qset.add(Q(project_id__in=p_qset.values_list('id', flat=True)[::1]), Q.OR)
        if docs_qset:
            docs_queryset = Attachment.objects.filter(organization=company, is_delete=False).filter(docs_qset)
            docs_queryset = docs_queryset.order_by('-created_at')
            queryset = self.filter_queryset(docs_queryset)
            context = self.paginate_queryset(queryset)
            serializer = AttachmentListSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def create(self, request, *args, **kwargs):
        if request.data.get('document') and (
            request.data.get("document_name").split('.')[-1].lower()
            not in [
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
            or (request.data.get('document').size > 304857000)
        ):
            return Response({"detail": "Please Upload valid document"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            DocumentBasicSerializer(instance, context={'request': request}).data, status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        attachment = self.get_object()
        if not attachment.content_type:
            if attachment.created_by == request.user:
                attachment.is_delete = True
                attachment.save()
                content = {"detail": "Your file has been " "successfully deleted"}
                return Response(content, status=status.HTTP_204_NO_CONTENT)
        else:
            permission = attachment.content_type.model + "_delete-doc"
            if GroupAndPermission.objects.filter(
                group=request.user.group,
                company=request.user.company,
                has_permission=True,
                permission__slug=permission,
            ).exists():
                attachment.is_delete = True
                attachment.save()
                content = {"detail": "Your file has been " "successfully deleted"}
                return Response(content, status=status.HTTP_204_NO_CONTENT)
        content = {"detail": "You don't have permission to " "perform this action"}
        return Response(content, status=status.HTTP_403_FORBIDDEN)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def rename(self, request, *args, **kwargs):
        # only rename the document
        partial = True
        doc_instance = self.get_object()
        updating_data = {}
        if request.data.get('document_name', ''):
            # set Document name string and validation with prev type of file
            if doc_instance.document_name:
                document_name_spit = request.data.get('document_name').split('.')
                updating_data['document_name'] = (
                    ".".join(document_name_spit[:-1] if len(document_name_spit) > 1 else document_name_spit[-1:])
                    + "."
                    + doc_instance.document_name.split('.')[-1]
                )
            else:
                if doc_instance.document.name:
                    updating_data['document_name'] = (
                        ".".join(request.data.get('document_name').split('.')[:-1])
                        + "."
                        + doc_instance.document.name.split('.')[-1]
                    )
                else:
                    updating_data['document_name'] = request.data.get('document_name')
        serializer = self.get_serializer(doc_instance, data=updating_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        AuditHistoryCreate("attachment", doc_instance.id, request.user, "Document renamed by")
        return Response(serializer.data, status=status.HTTP_200_OK)


class TagViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all tags of my organisation

    * API to search tags
    ```
    To search tag pass *tag*:
        url would be like `tags/?search=test`
    ```

    create:
    API to create new tag

    * `tag` is a name of tag
    * `organization` is id of currant user's organization

    delete:
    * API to delete tag
    ```
    To delete tag pass tag's ID:
    ```
    """

    model = Tag
    permission_classes = (
        IsAuthenticated,
        TagPermission,
    )
    filterset_class = TagFilterSet
    filter_backends = (filters.DjangoFilterBackend, SearchFilter)
    search_fields = ['tag']
    serializer_class = TagCreateSerializer
    http_method_names = ['post', 'get', 'patch', 'delete']

    def get_queryset(self):
        queryset = Tag.objects.none()
        user = self.request.user
        company = user.company
        if company:
            queryset = Tag.objects.filter(organization=company).order_by('tag')
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return TagCreateSerializer
        if self.action == 'partial_update':
            return TagBasicSerializer
        if self.action == 'list':
            return TagBasicSerializer
        elif self.action == 'retrieve':
            return TagCountDetailSerializer
        return TagDetailSerializer

    def partial_update(self, request, *args, **kwargs):
        partial = True
        if not (request.user.is_owner or request.user.group.is_company_admin):
            response = {"detail": "You don't have permission " "to perform this action"}
            return Response(response, status.HTTP_400_BAD_REQUEST)
        instance = get_object_or_404(self.get_queryset(), pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.tag = instance.tag.upper()
        instance.save()
        return Response(TagBasicSerializer(instance, context={'request': request}).data)

    def destroy(self, request, *args, **kwargs):
        if not (request.user.is_owner or request.user.group.is_company_admin):
            response = {"detail": "You don't have permission to " "perform this action"}
            return Response(response, status.HTTP_400_BAD_REQUEST)
        instance = get_object_or_404(self.get_queryset(), pk=int(kwargs.get('pk')))
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditHistoryViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all Audit History

    * API to search Audit History
    ```
    To Filter Audit History:
        model type:would be project,workflow,task,attachment,
                    servicedesk(request)
        model_id: it would be ID of project,workflow,task,
                  attachment,servicedesk
        ex:
            api/audit_history/?model_type=workflow&model_id=2
    ```
    """

    model = AuditHistory
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend,)
    queryset = AuditHistory.objects.all()
    serializer_class = AuditHistorySerializer
    http_method_names = ['get', 'post']

    def get_queryset(self):
        queryset = AuditHistory.objects.none()
        user = self.request.user
        company = user.company
        if company:
            queryset = AuditHistory.objects.filter(
                Q(by_user__company=company) | Q(by_servicedesk_user__organization=company)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'detail': 'Document downloaded successfully'}, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        offset_time = request.GET.get('offset_time')
        if not offset_time:
            return Response({'detail': "offset_time is required field"}, status=status.HTTP_400_BAD_REQUEST)
        # manual filter for model_reference and model_id
        # need to add authorization for request.user has permission to view.
        queryset = (
            self.get_queryset()
            .filter(model_reference=request.GET.get('model_type'))
            .filter(model_id=request.GET.get('model_id'))
            .order_by('-id')
        )
        serializer = self.get_serializer(queryset, many=True)
        response_data = {}
        response = []
        for instance in serializer.data:
            temp_dict = {}
            old_due_date = None
            new_due_date = None
            import dateutil.parser as dt_parse

            timezone = dt_parse.parse(instance['created_at']) + timedelta(minutes=int(offset_time))
            if instance.get('old_due_date'):
                old_due_date = dt_parse.parse(instance['old_due_date']) + timedelta(minutes=int(offset_time))
            if instance.get('new_due_date'):
                new_due_date = dt_parse.parse(instance['new_due_date']) + timedelta(minutes=int(offset_time))
            temp_dict['model_reference'] = instance['model_reference']
            temp_dict['model_id'] = instance['model_id']
            for key in instance['change_message']:
                # temp_dict['change_message'] = {}
                temp_dict['change_message'] = ReformatAuditHistory(instance, timezone, old_due_date, new_due_date, key)
            response.append(temp_dict)
        response_data['results'] = response
        return Response(response_data)


class AttachmentCopyOrMoveView(APIView):
    """
    API to move or copy an attachment.
    """

    def post(self, request, *args, **kwargs):
        # check if all fields are supplied in request data
        try:
            source_id = request.data.get('source')['id']
            source_type = request.data.get('source')['type']
            attachment_id = request.data.get('attachment_id')
            operation = request.data.get("operation")
            destination_id = request.data.get('destination')['id']
            destination_type = request.data.get('destination')['type']
        except Exception as e:
            print("exception:", e)
            content = {"detail": "Invalid data has been passed."}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)
        source_permission = source_type + "_upload-docs"
        destination_permission = destination_type + "_upload-docs"
        # restrict copy document for private task
        if operation.lower().strip() == "copy" and source_type.lower().strip() == "task":
            if Task.objects.filter(organization=request.user.company, id=int(source_id), is_private=True).exists():
                content = {"detail": "You can not copy document of private task "}
                return Response(content, status=status.HTTP_400_BAD_REQUEST)
        # check if the user has upload document permission for both
        # source and destination model category
        if (
            GroupAndPermission.objects.filter(
                group=request.user.group,
                company=request.user.company,
                has_permission=True,
                permission__slug=source_permission,
            ).exists()
            and GroupAndPermission.objects.filter(
                group=request.user.group,
                company=request.user.company,
                has_permission=True,
                permission__slug=destination_permission,
            ).exists()
        ):
            # call helper function to check if the user has
            # access to the resources passed in request data
            if user_attachment_authorization_permission(
                source_type, source_id, destination_type, destination_id, request.user
            ):
                # helper function to copy/move attachments
                attachment = attachment_copy_or_move(
                    destination_id, destination_type, source_id, source_type, attachment_id, operation, request.user
                )
                if attachment:
                    return Response(
                        AttachmentBasicSerializer(attachment, context={'request': request}).data,
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response({"detail": "Invalid operation"}, status=status.HTTP_400_BAD_REQUEST)
            content = {"detail": "You are not authorized to access these resources"}
            return Response(content, status=status.HTTP_403_FORBIDDEN)
        else:
            content = {"detail": "You don't have permission to perform this action"}
            return Response(content, status=status.HTTP_403_FORBIDDEN)


class WorkGroupViewSet(viewsets.ModelViewSet):
    """
    partial_update:
    API to update workgroup name
    { "name": "updating workgroup title" }

    list:
    * API to Sort WorkGroup by users_count/name
    ```
    Sort in ascending order : users_count/name
    Sort in descending order : -users_count/-name
    ```
    """

    model = WorkGroup
    permission_classes = (
        PermissionManagerPermission,
        WorkGoupPermission,
    )
    filterset_class = WorkGroupFilterSet
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter, SearchFilter)
    search_fields = [
        'name',
    ]
    ordering_fields = ['name', 'users_count']
    http_method_names = ['get', 'delete', 'patch']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = WorkGroup.objects.filter(organization=company).annotate(
            users_count=Count(
                'work_group',
                filter=Q(work_group__group_member__company=company, work_group__group_member__is_delete=False),
            )
        )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkGroupListSerializer
        elif self.action == 'retrieve':
            return WorkGroupListSerializer
        elif self.action == 'partial_update':
            return WorkGroupUpdateSerializer
        elif self.action == 'workgroup_add_members':
            return WorkGroupAddMemberSerializer
        elif self.action == 'workgroup_remove_members':
            return WorkGroupRemoveMemberSerializer
        return WorkGroupMemberCreateSerializer

    def partial_update(self, request, *args, **kwargs):
        partial = True
        instance = get_object_or_404(self.get_queryset(), pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        group_name = request.data.get('name', '').strip()
        if not group_name:
            return Response({'detail': "Please provide " "group name to update."}, status=status.HTTP_400_BAD_REQUEST)
        if group_name == instance.name:
            return Response(
                WorkGroupUpdateSerializer(instance, context={'request': request}).data, status=status.HTTP_200_OK
            )
        if WorkGroup.objects.filter(name__iexact=group_name, organization=request.user.company).exists():
            return Response(
                {'detail': "Sorry! But a group with the " "name already exist. Please try " "again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                WorkGroupUpdateSerializer(instance, context={'request': request}).data, status=status.HTTP_200_OK
            )

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def workgroup_add_members(self, request, pk=None):
        """
        action to add new member in workgroup.

        * add new member in workgroup, id,user id's list need
            to be passed.
        ```
        To add new member in workgroup:
        { "id": "workgroup's id" ,
         "group_members": [1,2,3]}
        ```
        """
        user_ids = request.data.get('group_members', [])
        if not user_ids:
            return Response(
                {'detail': "Please add members to " "add them in group."}, status=status.HTTP_400_BAD_REQUEST
            )
        users_ids = set(user_ids)
        users = list(users_ids)
        instance = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for user in users:
            user_instance = User.objects.filter(id=user, company=request.user.company, is_delete=False).first()
            if user_instance:
                workgroupmember_instance, created = WorkGroupMember.objects.get_or_create(
                    work_group=instance, group_member=user_instance
                )
                if created:
                    workgroup_assigned_notification(request.user, user_instance, instance)
                else:
                    pass
            else:
                pass
        return Response({'detail': "Group updated successfully."}, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def workgroup_remove_members(self, request, pk=None):
        """
        action to remove member in workgroup.

        * add remove member in workgroup, id,user id to be passed.
        ```
        To remove member in workgroup:
        { "id": "workgroup's id" ,
         "group_members": 1}
        ```
        """
        user_id = request.data.get('group_member', '')
        if not user_id:
            return Response(
                {'detail': "Please add members " "to remove them from group."}, status=status.HTTP_400_BAD_REQUEST
            )
        instance = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workgroup_member_instance = WorkGroupMember.objects.filter(
            work_group=instance, group_member__id=user_id
        ).first()
        if workgroup_member_instance:
            workgroup_member_instance.delete()
        else:
            return Response({'detail': "User does not belong " "to this group."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': "User removed successfully."}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        work_group = self.get_object()
        if (
            Project.objects.filter(
                organization=work_group.organization, assigned_to_group=work_group, assigned_to_users=None
            ).exists()
            or Workflow.objects.filter(
                organization=work_group.organization, assigned_to_group=work_group, assigned_to_users=None
            ).exists()
            or Task.objects.filter(
                organization=work_group.organization, assigned_to_group=work_group, assigned_to=None
            ).exists()
        ):
            return Response(
                {'detail': 'please re-assign ' 'project/workflow/task before ' 'deleting the group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            work_group.delete()
            return Response(status=status.HTTP_200_OK)


class WorkGroupMemberViewSet(viewsets.ModelViewSet):
    model = WorkGroupMember
    permission_classes = (
        PermissionManagerPermission,
        WorkGroupMemberPermission,
    )
    filter_backends = (OrderingFilter,)
    ordering_fields = [
        'work_group__name',
    ]
    http_method_names = ['post']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = WorkGroupMember.objects.filter(work_group__organization=company)
        return queryset

    def get_serializer_class(self):
        if self.action == 'workgroup_create':
            return WorkGroupMemberCreateSerializer
        return WorkGroupMemberCreateSerializer

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def workgroup_create(self, request, pk=None):
        """
        action to create a new workgroup.

        * add create a new workgroup, name of workgroup,user
            id's list need to be passed.
        ```
        To add new member in workgroup:
        { "name": "workgroup's name" ,
         "group_members": [1,2,3]}
        ```
        """
        group_name = request.data.get('name', '').strip()
        if not group_name:
            return Response({'detail': "Please provide group " "name to create."}, status=status.HTTP_400_BAD_REQUEST)
        user_ids = request.data.get('group_members', [])
        if not user_ids:
            return Response({'detail': "Please add members to " "create a group."}, status=status.HTTP_400_BAD_REQUEST)
        users_ids = set(user_ids)
        users = list(users_ids)
        try:
            instance = WorkGroup.objects.create(name=group_name, organization=request.user.company)
            for user in users:
                user_instance = User.objects.filter(id=user, company=request.user.company, is_delete=False).first()
                if user_instance:
                    WorkGroupMember.objects.create(work_group=instance, group_member=user_instance)
                    workgroup_assigned_notification(request.user, user_instance, instance)
                else:
                    pass
            return Response({'detail': "Your Group created " "successfully."}, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            print("exception:", e)
            return Response(
                {'detail': "Sorry! But a group with the " "name already exist. Please try " "again."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserWorkGroupViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    API to list all group that i am a part of

    * API to Sort group
    ```
    To sort groups
    Sorting fields: 'name','users_count',
    e.g : ascending by name > ordering=name
         descending by name > ordering=-name
    e.g : ascending by users_count > ordering=users_count
         descending by users_count > ordering=-users_count
    ```
    """

    permission_classes = (
        UserWorkGroupPermissionCustom,
        IsAuthenticated,
    )
    filter_backends = (OrderingFilter,)
    ordering_fields = [
        'name',
        'users_count',
    ]

    def get_queryset(self):
        user = self.request.user
        company = user.company
        workgroup_instance = WorkGroup.objects.filter(organization=company).annotate(
            users_count=Count(
                'work_group',
                filter=Q(work_group__group_member__company=company, work_group__group_member__is_delete=False),
            )
        )
        queryset = workgroup_instance.filter(group_members=user)
        return queryset

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        user = request.user
        group = user.group
        company = user.company
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        # total number of task under workflow based on my permission
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all',
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            task_queryset = Task.objects.filter(q_obj).distinct('id').values_list('id', flat=True)
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view',
        ).exists():
            task_queryset = (
                Task.objects.filter(
                    Q(organization=user.company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                )
                .distinct('id')
                .values_list('id', flat=True)
            )
        else:
            task_queryset = Task.objects.none()
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            task_queryset = task_queryset.exclude(status__in=[3, 4])
        serializer = UserWorkGroupListSerializer(
            context, context={'request': request, 'task_queryset': task_queryset}, many=True
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=[
            'get',
        ],
    )
    def workgroup_details_statistic(self, request, pk):
        """
        ```
        > API will return following detail for selected workgroup
        * total number of task as *all_task*
        * total number of completed task as *completed_task*
        * total number of task which has low importance as *low*
        * total number of task which has mid importance as *mid*
        * total number of task which has high importance as *high*
        * name of the work group *group_name*
        ```
        """
        user = request.user
        group = user.group
        company = user.company
        instance_group = get_object_or_404(self.filter_queryset(self.get_queryset()), pk=pk)
        task_queryset = Task.objects.filter(assigned_to_group=instance_group)
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all',
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            task_queryset = task_queryset.filter(q_obj).distinct('id')
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
        elif GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view',
        ).exists():
            task_queryset = task_queryset.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            )
            if not GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True,
            ).exists():
                task_queryset = task_queryset.exclude(status__in=[3, 4])
        else:
            context = {
                'low': 0,
                'med': 0,
                'high': 0,
                'all_task': 0,
                'completed_task': 0,
                'group_name': instance_group.name,
            }
            return Response(context, status=status.HTTP_200_OK)
        accessible_task_qset = Task.objects.filter(pk__in=task_queryset.values_list('id', flat=True).distinct())
        low = accessible_task_qset.filter(importance=1).exclude(status__in=[3, 4]).count()
        med = accessible_task_qset.filter(importance=2).exclude(status__in=[3, 4]).count()
        high = accessible_task_qset.filter(importance=3).exclude(status__in=[3, 4]).count()
        all_task = accessible_task_qset.count()
        comp_task = accessible_task_qset.filter(status__in=[3, 4]).count()
        context = {
            'low': low,
            'med': med,
            'high': high,
            'all_task': all_task,
            'completed_task': comp_task,
            'group_name': instance_group.name,
        }
        return Response(context, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        instance = get_object_or_404(self.get_queryset(), pk=int(kwargs.get('pk')))
        serializer = WorkGroupDetailSerializer(instance, context={'request': request})
        return Response(serializer.data)


class CompanyWorkGroupViewSet(viewsets.ModelViewSet):
    """
    list:

    * API to search group by name
    ```
    To sort groups
    Sorting fields: 'name'
    e.g : ascending by name > ordering=name
         descending by name > ordering=-name
    To search group by name > /?search=codal(group name)
    To search group > ?group=1,2(id of group)
    To search group by user > ?group_member=1,2(user id)
    ```
    """

    model = WorkGroup
    permission_classes = (
        IsAuthenticated,
        CompanyWorkGroupPermission,
    )
    filterset_class = CompanyWorkGroupFilterSet
    filter_backends = (filters.DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = [
        'name',
    ]
    ordering_fields = [
        'name',
    ]
    http_method_names = ['get']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = WorkGroup.objects.filter(organization=company)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyWorkGroupBasicSerializer
        elif self.action == 'retrieve':
            return CompanyWorkGroupBasicSerializer
        return CompanyWorkGroupBasicSerializer


class ServiceDeskUserViewSet(viewsets.ModelViewSet):
    """
    create:
    * `API to create new Request`
    ```
    * `name` is required filed enter name of user.
    * `email` is required filed in 'user_email'.
    * `Phone number` is not required filed in 'user_phone_number'.
    * `title`: title of request is not required filed
    ```
    """

    permission_classes = (
        AllowAny,
        ServiceDeskPermission,
    )
    http_method_names = ['post']

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceDeskUserCreateSerializer
        return ServiceDeskUserCreateSerializer

    def create(self, request, *args, **kwargs):
        req_token = request.data.get('captch', '').strip()
        if not req_token:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
        IP_Add = get_client_ip(request)
        r = requests.post(
            settings.DRF_RECAPTCHA_VERIFY_ENDPOINT,
            data={'secret': settings.DRF_RECAPTCHA_SECRET_KEY, 'response': req_token, 'remoteip': IP_Add},
        )
        if not json.loads(r.content.decode())['success']:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
        user_email = request.data.get('user_email', '').lower().strip()
        if not user_email:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user_obj = ServiceDeskUserInformation.objects.filter(
                user_email__iexact=user_email, organization=Organization.objects.first()
            ).first()
            if user_obj:
                if user_obj.is_expire:
                    user_obj.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                    user_obj.expiration_date = timezone.now() + timedelta(7)
                    user_obj.is_expire = False
                user_obj.user_name = serializer.data.get('user_name')
                user_obj.user_phone_number = serializer.data.get('user_phone_number')
                user_obj.save()
                return Response(data={'user_id': str(user_obj.access_token)}, status=status.HTTP_201_CREATED)
            instance = serializer.save()
            instance.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            # set 7 day expire date
            instance.expiration_date = timezone.now() + timedelta(7)
            instance.save()
            return Response(data={'user_id': str(instance.access_token)}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeskAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = (
        AllowAny,
        ServiceDeskAttachmentPermission,
    )
    parser_classes = (FormParser, MultiPartParser, JSONParser)

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceDeskAttachmentCreateSerializer
        return ServiceDeskAttachmentCreateSerializer

    def create(self, request, *args, **kwargs):
        req_token = request.data.get('captch', '').strip()
        if req_token:
            IP_Add = get_client_ip(request)
            r = requests.post(
                settings.DRF_RECAPTCHA_VERIFY_ENDPOINT,
                data={'secret': settings.DRF_RECAPTCHA_SECRET_KEY, 'response': req_token, 'remoteip': IP_Add},
            )
            if not json.loads(r.content.decode())['success']:
                return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
            else:
                pass
        document = request.FILES.getlist('document', [])
        auth_token = request.data.get('auth', '').strip()
        if auth_token and document:
            request_obj = ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=False).first()
            if not request_obj:
                return Response({"detail": "Invalid token."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response(data={'doc_id': [str(i.id) for i in instance]}, status=status.HTTP_201_CREATED)
        else:
            return Response({"detail": "Invalid data."}, status=status.HTTP_406_NOT_ACCEPTABLE)


class SubmitServiceDeskRequestViewSet(viewsets.ModelViewSet):
    """
    create:
    * `API to create new Request`
    ```
    * 'captch' and 'auth' are required to create a request
    * `description`: description of request is required filed
    * `requested_due_date` is required filed
        *date format:-"2019-10-09T18:30:00Z"
    * `attachments` is list of attachment id [1,3,4] not required filed
    * You can set `priority` level of request `request_priority`
        not required filed
    * request_priority values ==> 1: Low, 2: Med, 3: High
    * `assigned_to` is name of user not required filed
    ```
    """

    permission_classes = (
        AllowAny,
        ServiceDeskPermission,
    )
    http_method_names = ['post']

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceDeskRequestCreateSerializer
        return ServiceDeskRequestCreateSerializer

    def create(self, request, *args, **kwargs):
        req_token = request.data.get('captch', '').strip()
        if req_token:
            IP_Add = get_client_ip(request)
            r = requests.post(
                settings.DRF_RECAPTCHA_VERIFY_ENDPOINT,
                data={'secret': settings.DRF_RECAPTCHA_SECRET_KEY, 'response': req_token, 'remoteip': IP_Add},
            )
            if not json.loads(r.content.decode())['success']:
                return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
            else:
                pass
        user_info = request.data.get('auth', '')
        if not user_info:
            return Response({'detail': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        send_notification_to_user.delay(instance)
        ServiceDeskRequestAuditHistory("servicedeskrequest", instance.id, instance.user_information, "Submitted by")
        new_request_notification_to_team_member.delay(instance)
        if instance.service_desk_request_attachment:
            company = Organization.objects.first()
            content_type = ContentType.objects.get(app_label='projects', model='servicedeskrequest')
            user_obj = instance.user_information
            created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
            for document_obj in instance.service_desk_request_attachment.all():
                attachment_obj = Attachment(
                    organization=company, object_id=instance.id, content_type=content_type, uploaded_by=user_obj
                )
                name = document_obj.document.name.split('.')[-1]
                random_doc_name = get_random_string(20) + "." + name
                with default_storage.open(document_obj.document.name, 'rb') as f:
                    attachment_obj.document_name = document_obj.document_name
                    attachment_obj.document.save(random_doc_name, File(f))
                    f.close()
                attachment_obj.save()
                doc_uploaded_message = {"Date uploaded:": created_at + " " + "by" + " " + user_obj.user_name}
                AuditHistory.objects.create(
                    model_reference="attachment",
                    model_id=attachment_obj.id,
                    by_servicedesk_user=user_obj,
                    change_message=doc_uploaded_message,
                )

                document_obj.is_delete = True
                document_obj.save()
        return Response(
            {
                'detail': 'Your Request was successfully submitted to '
                '{}.'.format(instance.user_information.organization)
            },
            status=status.HTTP_201_CREATED,
        )


class RequestPortalViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all Request of my organization

    * API to Sort Request by fields
    ```
    To sort Request by any field pass that field name in ordering
    Sorting fields: 'request_priority','subject',
                    'user_information__user_email',
                    'assigned_to',
     'requested_due_date', 'id'
    e.g : ascending by request_priority > ordering=request_priority
         descending by request_priority > ordering=-request_priority
    ```
    delete:
    API to delete any request of my organization
    ```
    To delete request pass id's of the request in request_delete
      url: api/company_service_desk_portal/54,55/
    ```
    """

    permission_classes = (
        IsAuthenticated,
        RequestPermission,
    )
    filter_backends = (OrderingFilter,)
    ordering_fields = [
        'id',
        'request_priority',
        'subject',
        'user_information__user_email',
        'assigned_to',
        'requested_due_date',
    ]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        if not company:
            return None
        queryset = ServiceDeskRequest.objects.filter(user_information__organization=company, is_delete=False).order_by(
            '-id'
        )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return RequestListSerializer
        elif self.action == 'retrieve':
            return RequestDetailsSerializer
        elif self.action == 'bulk_task_creation':
            return TaskCreateSerializer
        elif self.action == 'create_new_request':
            return AssociateNewRequestSerializer
        if self.action == 'request_add_messages':
            return PendingRequestMessageSerializer
        return RequestListSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            for obj_id in self.kwargs['pk'].split(','):
                instance = get_object_or_404(self.get_queryset(), pk=int(obj_id))
                instance.is_delete = True
                instance.save()
        except Exception as e:
            print("exception:", str(e))
            return Response({'detail': "Invalid request."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @list_route(methods=['POST'])
    def bulk_task_creation(self, request):
        """
        * API to convert request tickets in to Task
        ```
        pass params that needs to be pass in order to
            create a new task inside *data* as per below
        pass id's of request tickets in *tickets*
            ex. "tickets":[1,2,3]
        {
        "data": [
                {
                  "name": "string",
                  "assigned_to": 0,
                  "attachments": ["string"],
                  "importance": 0,
                  "status": "5",
                  "task_tags": ["string"],
                  "due_date": "string",
                  "workflow": 0,
                  "description": "string",
                  "attorney_client_privilege": true,
                  "work_product_privilege": true,
                  "confidential_privilege": true,
                  "assigned_to_group": ["string"]
                },
                {
                  "name": "string",
                  "assigned_to": 0,
                  "attachments": ["string"],
                  "importance": 0,
                  "status": "5",
                  "task_tags": ["string"],
                  "due_date": "string",
                  "workflow": 0,
                  "description": "string",
                  "attorney_client_privilege": true,
                  "work_product_privilege": true,
                  "confidential_privilege": true,
                  "assigned_to_group": ["string"]
                }
                ],
        "tickets":["string"]
        }
        ```
        """
        user = request.user
        ticket_data = request.data.get('tickets')
        tasks_data = request.data.get('data')
        if len(ticket_data) is not len(tasks_data):
            return Response({"detail": "Invalid data."}, status=status.HTTP_400_BAD_REQUEST)
        obj_count = 0
        for task_data in tasks_data:
            ticket_instance = get_object_or_404(self.get_queryset(), pk=int(ticket_data[obj_count]))
            serializer = self.get_serializer(data=task_data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            if instance.status != 5:
                instance.status = 5
                instance.save()
            request_obj = ServiceDeskExternalRequest.objects.create(
                task=instance,
                servicedeskuser=ticket_instance.user_information,
                created_by=user,
                service_desk_request=ticket_instance,
            )
            message_obj = ServiceDeskRequestMessage.objects.create(
                reply_by_servicedeskuser=ticket_instance.user_information,
                task=instance,
                message=ticket_instance.description,
                servicedesk_request=request_obj.service_desk_request,
                is_external_message=True,
                is_first_message=True,
            )
            ticket_instance.is_delete = True
            instance.save()
            ticket_instance.save()
            # inform NRU that their ticket request has been
            # "picked up" by our team member(s).
            send_notification_to_servicedeskuser.delay(request_obj, message_obj, False)
            obj_count += 1
        response = {"detail": "The Request was successfully " "converted into a task!."}
        return Response(response, status=status.HTTP_201_CREATED)

    # @action(detail=False, methods=['post', ])
    # def create_new_request(self, request, *args, **kwargs):
    #     """
    #     * To Associate Request to task
    #     ```
    #     * user_name is required
    #     * user_email is required
    #     * requested_due_date is required
    #     * description is required
    #     * subject should be request name(required)
    #     * attachments are optional
    #     ```
    #     """
    #     user = request.user
    #     company = user.company
    #     serializer = self.get_serializer(data=request.data)
    #     if serializer.is_valid(raise_exception=True):
    #         user_email = serializer.data['user_email'].lower().strip()
    #         servicedesk_user =
    #         ServiceDeskUserInformation.objects.filter(
    #             user_email=user_email).first()
    #         if not servicedesk_user:
    #             user_name = serializer.data['user_name']
    #             access_token =
    #             str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
    #             expiration_date = timezone.now() + timedelta(7)
    #             servicedesk_user =
    #             ServiceDeskUserInformation.objects.create(
    #                 user_email=user_email,
    #                 user_name=user_name,
    #                 organization=company,
    #                 expiration_date=expiration_date,
    #                 access_token=access_token)
    #         user_information = servicedesk_user
    #         subject = serializer.data['subject']
    #         description = serializer.data['description']
    #         requested_due_date = serializer.data['requested_due_date']
    #         request_obj = ServiceDeskRequest.objects.create(
    #             user_information=user_information,
    #             subject=subject,
    #             description=description,
    #             requested_due_date=requested_due_date,
    #             is_delete=False,
    #             is_internal_request=False)
    #         # send notification to NRU for request submitted successfully
    #         send_notification_to_user.delay(request_obj)
    #         if 'attachments' in serializer.data.keys():
    #             content_type = ContentType.objects.get(
    #             app_label='projects', model='servicedeskrequest')
    #             # Document Uploaded to Request
    #             for attachment in serializer.data['attachments']:
    #                 attachment_obj = Attachment.objects.filter(
    #                 id=attachment,organization=company,
    #                  is_delete=False,created_by=user).first()
    #                 if attachment_obj:
    #                     attachment_obj.content_type = content_type
    #                     attachment_obj.object_id = request_obj.id
    #                     attachment_obj.save()
    #         AuditHistoryCreate("servicedeskrequest",
    #         request_obj.id, user, "Submitted by")
    #         return Response({'detail': 'Your Request was
    #         submitted successfully!.'},
    #                         status=status.HTTP_201_CREATED)
    #     else:
    #         return Response(serializer.errors,
    #                         status=status.HTTP_400_BAD_REQUEST)

    # @action(detail=False,  methods=['post', ])
    # def request_add_messages(self, request, pk=None):
    #     """
    #     * To add new Message to request for NRU
    #     ```
    #     * servicedesk_request is required(id of request)
    #     * message is required
    #     ```
    #     """
    #     user = self.request.user
    #     company = user.company
    #     queryset = ServiceDeskRequest.objects.filter(
    #         user_information__organization=company, is_delete=False)
    #     serializer = self.get_serializer(data=request.data)
    #     if serializer.is_valid(raise_exception=True):
    #         instance = get_object_or_404(queryset,
    #         pk=serializer.data['servicedesk_request'])
    #         message_obj = ServiceDeskRequestMessage.
    #         objects.create(
    #             message=serializer.data['message'],
    #             servicedesk_request=instance,
    #             reply_by_servicedeskuser=instance.user_information)
    #         return Response({'detail': str(message_obj.id)},
    #                         status=status.HTTP_201_CREATED)
    #     else:
    #         return Response(serializer.errors,
    #                         status=status.HTTP_400_BAD_REQUEST)
    #
    # @action(detail=False, methods=['get', ])
    # def request_all_messages(self, request, *args, **kwargs):
    #     """
    #     * To view all Message to request
    #     ```
    #     * request_id is required(id of request)
    #     ```
    #     """
    #     user = self.request.user
    #     company = user.company
    #     request_id = self.request.query_params.get(
    #     'request_id', '').strip()
    #     id = self.request.query_params.get('id__gte', '')
    #     if not request_id or not str(request_id).isdigit():
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
    #     queryset = ServiceDeskRequest.objects.filter(
    #         user_information__organization=company,
    #         is_delete=False).order_by('-id')
    #     instance = get_object_or_404(queryset, pk=int(request_id))
    #     message_objs =
    #     ServiceDeskRequestMessage.objects.filter(
    #         servicedesk_request=instance
    #         ).order_by('-id')
    #     if id:
    #         message_objs = message_objs.filter(id__gte=id)
    #         context = self.paginate_queryset(message_objs)
    #         serializer = MessageListSerializer(
    #             context, many=True, context={'request': request})
    #         return self.get_paginated_response(serializer.data)
    #     context = self.paginate_queryset(message_objs)
    #     serializer = MessageListSerializer(
    #         context, many=True, context={'request': request})
    #     return self.get_paginated_response(serializer.data)

    @list_route(methods=['POST'])
    def task_request_create(self, request):
        """
        * API to send bulk invitation
        ```
        {
        "task": {
                  "name": "string",
                  "assigned_to": 0,
                  "attachments": ["string"],
                  "importance": 0,
                  "status": "5",
                  "task_tags": ["string"],
                  "due_date": "string",
                  "workflow": 0,
                  "description": "string",
                  "attorney_client_privilege": true,
                  "work_product_privilege": true,
                  "confidential_privilege": true,
                  "assigned_to_group": ["string"]
                },
        "request": {
                 "user_name": "string",
                  "user_email": "string",
                  "requested_due_date": "string",
                  "description": "string",
                  "subject": "string",
                }
        }
        ```
        """
        user = request.user
        company = user.company
        task_data = request.data.get('task', '')
        request_data = request.data.get('request', '')
        if not task_data or not request_data:
            return Response({"detail": "Invalid data."}, status=status.HTTP_400_BAD_REQUEST)
        request_serializer = AssociateNewRequestSerializer(data=request_data)
        if request_serializer.is_valid(raise_exception=True):
            user_obj = ServiceDeskUserInformation.objects.filter(
                user_email=request_serializer.data['user_email']
            ).first()
            if not user_obj:
                user_name = request_serializer.data['user_name']
                user_email = request_serializer.data['user_email']
                access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                expiration_date = timezone.now() + timedelta(7)
                user_obj = ServiceDeskUserInformation.objects.create(
                    user_email=user_email,
                    user_name=user_name,
                    organization=company,
                    expiration_date=expiration_date,
                    access_token=access_token,
                )
            description = request_serializer.data['description']
            requested_due_date = request_serializer.data['requested_due_date']
            request_obj = ServiceDeskRequest.objects.create(
                user_information=user_obj,
                description=description,
                requested_due_date=requested_due_date,
                is_delete=True,
                is_internal_request=True,
            )
            task_serializer = TaskCreateSerializer(data=task_data, context={'request': request})
            if task_serializer.is_valid(raise_exception=True):
                task_instance = task_serializer.save()
                request_obj.request_priority = task_instance.importance
                request_obj.subject = task_instance.name
                request_obj.save()
                external_request_obj = ServiceDeskExternalRequest.objects.create(
                    task=task_instance, servicedeskuser=user_obj, created_by=user, service_desk_request=request_obj
                )
                message_obj = ServiceDeskRequestMessage.objects.create(
                    created_by_user=user, task=task_instance, message=description
                )
                send_notification_to_servicedeskuser.delay(external_request_obj, message_obj, False)
                task_instance.status = 5
                task_instance.save()
                # send notification to NRU for request submitted
                # successfully
                request_submit_notification.delay(request_obj, user, task_instance, "task")
                AuditHistoryCreate("task", task_instance.id, user, "Submitted by")
                AuditHistoryCreate("task", task_instance.id, user, "External Request at")
                response = {"detail": "Task created and linked " "to request successfully!."}
                return Response(response, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class PendingRequestViewSet(viewsets.ModelViewSet):
    """
    list:
    * API to list all Pending Request of mine as NRU
    ```
    To list all Pending Request of mine as
        NRU pass token in request as *auth*
    ```
    """

    permission_classes = (AllowAny, PendingRequestPermission)

    def get_queryset(self):
        user_token = self.request.query_params.get('auth', '').strip()
        if not user_token:
            return ServiceDeskRequest.objects.none()
        queryset = ServiceDeskRequest.objects.filter(
            is_delete=False,
            user_information__is_expire=False,
            user_information__access_token=user_token,
            is_internal_request=False,
        )
        if queryset:
            return queryset
        return ServiceDeskRequest.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return ServiceDeskListSerializer
        # if self.action == 'retrieve':
        #     return ServiceDeskDetailsSerializer
        # if self.action == 'add_document_to_pending_request':
        #     return ServiceDeskRequestDocumentUploadSerializer
        # if self.action == 'pending_request_add_messages':
        #     return PendingRequestMessageSerializer
        return RequestListSerializer

    # def destroy(self, request, *args, **kwargs):
    #     request_obj = self.get_object()
    #     request_obj.is_delete = True
    #     request_obj.save()
    #     return Response(status=status.HTTP_204_NO_CONTENT)

    # @action(detail=True, methods=['patch', ])
    # def add_document_to_pending_request(self, request, pk=None):
    #     """
    #     * To Associate Document to pending request
    #     ```
    #     * auth is required
    #     * attachments is required
    #     ```
    #     """
    #     company = Organization.objects.first()
    #     user_token = request.data.get('auth', '')
    #     if not user_token:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
    #     queryset = ServiceDeskRequest.objects.filter(
    #     is_delete=False, user_information__is_expire=False,
    #     user_information__access_token=user_token,
    #     is_internal_request=False)
    #     instance = get_object_or_404(queryset, pk=pk)
    #     serializer = self.get_serializer(data=request.data)
    #     if serializer.is_valid():
    #         content_type = ContentType.objects.get(
    #         app_label='projects', model='servicedeskrequest')
    #         for attach_id in serializer.data['attachments']:
    #             document_obj =
    #             ServiceDeskAttachment.objects.filter(
    #                 id=attach_id,
    #                 uploaded_by=instance.user_information.user_email,
    #                 can_remove=True,
    #                 is_delete=False).first()
    #             if document_obj:
    #                 attachment_obj =
    #                 Attachment.objects.create(
    #                 organization=company,
    #                  object_id=instance.id,
    #                  content_type=content_type,
    #                  uploaded_by=instance.user_information)
    #                 random_doc_name = get_random_string(20) + "." + \
    #                                   document_obj.document.
    #                                   name.split('.')[-1]
    #                 with default_storage.open(
    #                 document_obj.document.name,
    #                 'rb') as f:
    #                     attachment_obj.document_name =
    #                     document_obj.document_name
    #                     attachment_obj.document.save(
    #                     random_doc_name, File(f))
    #                     f.close()
    #                 document_obj.is_delete = True
    #                 document_obj.can_remove = False
    #                 document_obj.save()
    #         return Response(
    #             {'detail': 'Document uploaded successfully!.'},
    #             status=status.HTTP_201_CREATED)
    #     else:
    #         return Response(serializer.errors,
    #                         status=status.HTTP_400_BAD_REQUEST)
    #
    # @action(detail=False,  methods=['post', ])
    # def pending_request_add_messages(self, request, pk=None):
    #     """
    #     * To add new Message to pending request
    #     ```
    #     * auth is required
    #     * servicedesk_request is required(id of request)
    #     * message is required
    #     ```
    #     """
    #     user_token = request.data.get('auth', '').strip()
    #     if not user_token:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
    #     queryset = ServiceDeskRequest.objects.filter(
    #     is_delete=False,
    #     user_information__is_expire=False,
    #     user_information__access_token=user_token,
    #     is_internal_request=False)
    #     serializer = self.get_serializer(data=request.data)
    #     if serializer.is_valid(raise_exception=True):
    #         instance = get_object_or_404(queryset,
    #         pk=serializer.data['servicedesk_request'])
    #         message_obj =
    #         ServiceDeskRequestMessage.objects.create(
    #             message=serializer.data['message'],
    #             servicedesk_request=instance,
    #             reply_by_servicedeskuser=instance.user_information)
    #         return Response({'detail': str(message_obj.id)},
    #                         status=status.HTTP_201_CREATED)
    #     else:
    #         return Response(serializer.errors,
    #                         status=status.HTTP_400_BAD_REQUEST)
    #
    # @action(detail=False, methods=['get', ])
    # def pendingrequest_messages(self, request, *args, **kwargs):
    #     """
    #     * To view all Message to pending request
    #     ```
    #     * auth is required
    #     * request_id is required(id of request)
    #     ```
    #     """
    #     user_token = self.request.query_params.get(
    #     'auth', '').strip()
    #     request_id = self.request.query_params.get(
    #     'request_id', '').strip()
    #     id = self.request.query_params.get('id__gte', '')
    #     if not user_token or not request_id:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
    #     queryset = ServiceDeskRequest.objects.filter(
    #     is_delete=False,
    #     user_information__is_expire=False,
    #     user_information__access_token=user_token,
    #     is_internal_request=False)
    #     if not str(request_id).isdigit():
    #         raise Http404
    #     instance = get_object_or_404(queryset, pk=int(request_id))
    #     message_objs =
    #     ServiceDeskRequestMessage.objects.filter(
    #         servicedesk_request=instance).order_by('-id')
    #     if id:
    #         message_objs = message_objs.filter(id__gte=id)
    #         context = self.paginate_queryset(message_objs)
    #         serializer = MessageListSerializer(
    #             context, many=True, context={'request': request})
    #         return self.get_paginated_response(serializer.data)
    #     context = self.paginate_queryset(message_objs)
    #     serializer = MessageListSerializer(
    #         context, many=True, context={'request': request})
    #     return self.get_paginated_response(serializer.data)


class SubmittedRequestViewSet(viewsets.ModelViewSet):
    """
    list:
    * API to list all Request of mine converted into task as NRU
    ```
    To list all Request of mine converted into task as
    NRU pass token in request as *auth*

    * Filter task by status
        Status values ==> 1: New, 2: In-Progress, 3: Completed,
        4: Archived, 5: External Request 6: External Update
        To filter Requests by current Request> task_status=1,2,5,6
        To filter task by New & Completed > task_status=3,4
    * Filter project/workflow by status
        Status values ==> 1: New, 2: Complete, 3: Archive,
        4: External Request 5: External Update
        To filter Requests by current Request> pw_status=1,2,5,6
        To filter task by New & Completed > pw_status=3,4

    ```
    """

    permission_classes = (AllowAny, SubmittedRequestPermission)

    def get_queryset(self):
        user_token = self.request.query_params.get('auth', '').strip()
        status = self.request.query_params.get('status', None)
        if not user_token or not status:
            return ServiceDeskExternalRequest.objects.none()
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        if queryset:
            if status.lower() == "archived":
                task_status = [3, 4]
                p_w_status = [2, 3]
            elif status.lower() == "active":
                task_status = [
                    1,
                    2,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                    32,
                    33,
                    34,
                ]
                p_w_status = [1, 4, 5]
            else:
                return ServiceDeskExternalRequest.objects.none()
            return queryset.filter(
                Q(task__status__in=task_status)
                | Q(workflow__status__in=p_w_status)
                | Q(project__status__in=p_w_status)
            ).distinct('id')
        return ServiceDeskExternalRequest.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return ServiceDeskExternalRequestListSerializer
        elif self.action == 'retrieve':
            return ServiceDeskExternalRequestDetailSerializer
        elif self.action == 'add_document_to_request':
            return ServiceDeskRequestDocumentUploadSerializer
        elif self.action == 'submitrequest_add_messages':
            return SubmitRequestMessageSerializer
        elif self.action == 'submitrequest_delete_messages':
            return MessageDeleteSerializer
        else:
            return ServiceDeskExternalRequestListSerializer

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def add_document_to_request(self, request, pk=None):
        """
        * To Associate Document with task/project/workflow
        ```
        * auth is required
        * attachments is required
        ```
        """
        user_token = request.data.get('auth', '')
        if not user_token:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        instance = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer(data=request.data)
        attachment_exist = False
        created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
        if serializer.is_valid():
            if instance.project:
                project_obj = instance.project
                if project_obj.status in [2, 3]:
                    return Response(
                        {'detail': 'You can not upload new ' 'document from completed request'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user_obj = instance.servicedeskuser
                content_type = ContentType.objects.get(app_label='projects', model='project')
                for attach_id in serializer.data['attachments']:
                    document_obj = ServiceDeskAttachment.objects.filter(
                        id=attach_id, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                    ).first()
                    if document_obj:
                        attachment_obj = Attachment(
                            organization=project_obj.organization,
                            object_id=project_obj.id,
                            content_type=content_type,
                            uploaded_by=user_obj,
                        )
                        name = document_obj.document.name.split('.')[-1]
                        random_doc_name = get_random_string(20) + "." + name
                        with default_storage.open(document_obj.document.name, 'rb') as f:
                            attachment_obj.document_name = document_obj.document_name
                            attachment_obj.document.save(random_doc_name, File(f))
                            f.close()
                        attachment_obj.save()
                        document_obj.is_delete = True
                        document_obj.can_remove = False
                        document_obj.save()
                        attachment_exist = True
                        doc_uploaded_message = {"Date uploaded:": created_at + " " + "by" + " " + user_obj.user_name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_uploaded_message,
                        )
                        doc_associated_message = {"Associated Project": project_obj.name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_associated_message,
                            model_name=project_obj.name,
                        )
                if attachment_exist:
                    project_obj.status = 5
                    project_obj.save()
                    project_status_change_message = {
                        "External Update at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="project",
                        model_id=project_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=project_status_change_message,
                    )
                    project_doc_uploaded_message = {
                        "Document Uploaded at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="project",
                        model_id=project_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=project_doc_uploaded_message,
                    )
                    project_attachment_uploaded_notification(project_obj, project_obj.owner)
                    if project_obj.assigned_to_users:
                        for project_user in project_obj.assigned_to_users.all():
                            if project_user != project_obj.owner:
                                project_attachment_uploaded_notification(project_obj, project_user)
                    if project_obj.assigned_to_group:
                        for projects_group in project_obj.assigned_to_group.all():
                            [
                                project_attachment_uploaded_notification(project_obj, group_member)
                                for group_member in projects_group.group_members.all()
                            ]
                return Response({'detail': 'Document uploaded successfully!.'}, status=status.HTTP_201_CREATED)
            elif instance.workflow:
                workflow_obj = instance.workflow
                if workflow_obj.status in [2, 3]:
                    return Response(
                        {'detail': 'You can not upload new ' 'document from completed ' 'request'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user_obj = instance.servicedeskuser
                content_type = ContentType.objects.get(app_label='projects', model='workflow')
                for attach_id in serializer.data['attachments']:
                    document_obj = ServiceDeskAttachment.objects.filter(
                        id=attach_id, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                    ).first()
                    if document_obj:
                        attachment_obj = Attachment(
                            organization=workflow_obj.organization,
                            object_id=workflow_obj.id,
                            content_type=content_type,
                            uploaded_by=user_obj,
                        )
                        name = document_obj.document.name.split('.')[-1]
                        random_doc_name = get_random_string(20) + "." + name
                        with default_storage.open(document_obj.document.name, 'rb') as f:
                            attachment_obj.document_name = document_obj.document_name
                            attachment_obj.document.save(random_doc_name, File(f))
                            f.close()
                        attachment_obj.save()
                        document_obj.is_delete = True
                        document_obj.can_remove = False
                        document_obj.save()
                        attachment_exist = True
                        doc_uploaded_message = {"Date uploaded:": created_at + " " + "by" + " " + user_obj.user_name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_uploaded_message,
                        )
                        doc_associated_message = {"Associated Workflow": workflow_obj.name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_associated_message,
                            model_name=workflow_obj.name,
                        )
                if attachment_exist:
                    workflow_obj.status = 5
                    workflow_obj.save()
                    workflow_status_change_message = {
                        "External Update at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="workflow",
                        model_id=workflow_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=workflow_status_change_message,
                    )
                    workflow_doc_uploaded_message = {
                        "Document Uploaded at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="workflow",
                        model_id=workflow_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=workflow_doc_uploaded_message,
                    )
                    workflow_attachment_uploaded_notification(workflow_obj, workflow_obj.owner)
                    if workflow_obj.assigned_to_users:
                        for workflow_user in workflow_obj.assigned_to_users.all():
                            if workflow_user != workflow_obj.owner:
                                workflow_attachment_uploaded_notification(workflow_obj, workflow_user)
                    if workflow_obj.assigned_to_group:
                        for workflow_group in workflow_obj.assigned_to_group.all():
                            [
                                workflow_attachment_uploaded_notification(workflow_obj, group_member)
                                for group_member in workflow_group.group_members.all()
                            ]
                return Response({'detail': 'Document uploaded successfully!.'}, status=status.HTTP_201_CREATED)
            if instance.task:
                task_obj = instance.task
                if task_obj.status in [3, 4]:
                    return Response(
                        {'detail': 'You can not upload new ' 'document from completed ' 'request'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user_obj = instance.servicedeskuser
                content_type = ContentType.objects.get(app_label='projects', model='task')
                for attach_id in serializer.data['attachments']:
                    document_obj = ServiceDeskAttachment.objects.filter(
                        id=attach_id, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                    ).first()
                    if document_obj:
                        attachment_obj = Attachment(
                            organization=task_obj.organization,
                            object_id=task_obj.id,
                            content_type=content_type,
                            uploaded_by=user_obj,
                        )
                        name = document_obj.document.name.split('.')[-1]
                        random_doc_name = get_random_string(20) + "." + name
                        with default_storage.open(document_obj.document.name, 'rb') as f:
                            attachment_obj.document_name = document_obj.document_name
                            attachment_obj.document.save(random_doc_name, File(f))
                            f.close()
                        attachment_obj.save()
                        document_obj.is_delete = True
                        document_obj.can_remove = False
                        document_obj.save()
                        attachment_exist = True
                        doc_uploaded_message = {"Date uploaded:": created_at + " " + "by" + " " + user_obj.user_name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_uploaded_message,
                        )
                        doc_associated_message = {"Associated Task": task_obj.name}
                        AuditHistory.objects.create(
                            model_reference="attachment",
                            model_id=attachment_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=doc_associated_message,
                            model_name=task_obj.name,
                        )
                if attachment_exist:
                    task_obj.status = 6
                    task_obj.save()
                    task_status_change_message = {
                        "External Update at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="task",
                        model_id=task_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=task_status_change_message,
                    )
                    task_doc_uploaded_message = {
                        "Document Uploaded at": created_at + " " + "by" + " " + user_obj.user_name
                    }
                    AuditHistory.objects.create(
                        model_reference="task",
                        model_id=task_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=task_doc_uploaded_message,
                    )
                    if task_obj.created_by == task_obj.assigned_to:
                        task_attachment_uploaded_notification(task_obj, task_obj.created_by, user_obj)
                    else:
                        task_attachment_uploaded_notification(task_obj, task_obj.created_by, user_obj)
                        task_attachment_uploaded_notification(task_obj, task_obj.assigned_to, user_obj)
                    if task_obj.assigned_to_group:
                        for task_group in task_obj.assigned_to_group.all():
                            [
                                task_attachment_uploaded_notification(task_obj, group_member, user_obj)
                                for group_member in task_group.group_members.all()
                            ]
                return Response({'detail': 'Document uploaded ' 'successfully!.'}, status=status.HTTP_201_CREATED)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def submitrequest_add_messages(self, request, pk=None):
        """
        * To add new Message to submitted request
        ```
        * auth is required
        * request_id is required(id of request)
        * either message or attachments is required
          eg: {'auth':'token','message':'' ,
              'request_id','attachments':[]}
        ```
        """
        user_token = request.data.get('auth', '').strip()
        if not user_token:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            instance = get_object_or_404(queryset, pk=serializer.data['request_id'])
            if instance.task:
                task_obj = instance.task
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    task=task_obj,
                    reply_by_servicedeskuser=instance.servicedeskuser,
                    is_external_message=True,
                    servicedesk_request=instance.service_desk_request,
                )
                if task_obj.status in [3, 4]:
                    completed_request_reply.delay(instance, task_obj, message_obj, "task")
                else:
                    task_notify_user_for_new_message.delay(instance, task_obj, message_obj)
                if task_obj.status not in [3, 4]:
                    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
                    user_obj = instance.servicedeskuser
                    history = created_at + " " + "by" + " " + user_obj.user_name
                    task_obj.status = 6
                    task_obj.save()
                    task_status_change_message = {"External Update at": history}
                    AuditHistory.objects.create(
                        model_reference="task",
                        model_id=task_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=task_status_change_message,
                    )
                    if 'attachments' in serializer.data.keys():
                        user_obj = instance.servicedeskuser
                        content_type = ContentType.objects.get(app_label='projects', model='task')
                        attachment_exist = False
                        for attachment in serializer.data['attachments']:
                            document_obj = ServiceDeskAttachment.objects.filter(
                                id=attachment, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                            ).first()
                            if document_obj:
                                attachment_obj = Attachment(
                                    organization=task_obj.organization,
                                    object_id=task_obj.id,
                                    content_type=content_type,
                                    uploaded_by=user_obj,
                                    message_document=message_obj,
                                )
                                random_doc_name = (
                                    get_random_string(20) + "." + document_obj.document.name.split('.')[-1]
                                )
                                with default_storage.open(document_obj.document.name, 'rb') as f:
                                    attachment_obj.document_name = document_obj.document_name
                                    attachment_obj.document.save(random_doc_name, File(f))
                                    f.close()
                                attachment_obj.save()
                                document_obj.is_delete = True
                                document_obj.can_remove = False
                                document_obj.save()
                                attachment_exist = True
                                doc_uploaded_message = {"Date uploaded:": history}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_uploaded_message,
                                )
                                doc_associated_message = {"Associated Task": task_obj.name}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_associated_message,
                                    model_name=task_obj.name,
                                )
                        if attachment_exist:
                            task_doc_uploaded_message = {"Document Uploaded at": history}
                            AuditHistory.objects.create(
                                model_reference="task",
                                model_id=task_obj.id,
                                by_servicedesk_user=user_obj,
                                change_message=task_doc_uploaded_message,
                            )
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            elif instance.workflow:
                workflow_obj = instance.workflow
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    workflow=workflow_obj,
                    reply_by_servicedeskuser=instance.servicedeskuser,
                    is_external_message=True,
                )
                if workflow_obj.status in [2, 3]:
                    completed_request_reply.delay(instance, workflow_obj, message_obj, "workflow")
                else:
                    workflow_notify_user_for_new_message.delay(instance, workflow_obj, message_obj)
                if workflow_obj.status in [1, 4, 5]:
                    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
                    user_obj = instance.servicedeskuser
                    history = created_at + " " + "by" + " " + user_obj.user_name
                    workflow_obj.status = 5
                    workflow_obj.save()
                    workflow_status_change_message = {"External Update at": history}
                    AuditHistory.objects.create(
                        model_reference="workflow",
                        model_id=workflow_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=workflow_status_change_message,
                    )
                    if 'attachments' in serializer.data.keys():
                        user_obj = instance.servicedeskuser
                        content_type = ContentType.objects.get(app_label='projects', model='workflow')
                        attachment_exist = False
                        for attachment in serializer.data['attachments']:
                            document_obj = ServiceDeskAttachment.objects.filter(
                                id=attachment, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                            ).first()
                            if document_obj:
                                attachment_obj = Attachment(
                                    organization=workflow_obj.organization,
                                    object_id=workflow_obj.id,
                                    content_type=content_type,
                                    uploaded_by=user_obj,
                                    message_document=message_obj,
                                )
                                random_doc_name = (
                                    get_random_string(20) + "." + document_obj.document.name.split('.')[-1]
                                )
                                with default_storage.open(document_obj.document.name, 'rb') as f:
                                    attachment_obj.document_name = document_obj.document_name
                                    attachment_obj.document.save(random_doc_name, File(f))
                                    f.close()
                                attachment_obj.save()
                                document_obj.is_delete = True
                                document_obj.can_remove = False
                                document_obj.save()
                                attachment_exist = True
                                doc_uploaded_message = {"Date uploaded:": history}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_uploaded_message,
                                )
                                doc_associated_message = {"Associated Workflow": workflow_obj.name}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_associated_message,
                                    model_name=workflow_obj.name,
                                )
                        if attachment_exist:
                            workflow_status_change_message = {"Document Uploaded at": history}
                            AuditHistory.objects.create(
                                model_reference="workflow",
                                model_id=workflow_obj.id,
                                by_servicedesk_user=user_obj,
                                change_message=workflow_status_change_message,
                            )
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            elif instance.project:
                project_obj = instance.project
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    project=project_obj,
                    reply_by_servicedeskuser=instance.servicedeskuser,
                    is_external_message=True,
                )
                if project_obj.status in [2, 3]:
                    completed_request_reply.delay(instance, project_obj, message_obj, "project")
                else:
                    project_notify_user_for_new_message.delay(instance, project_obj, message_obj)
                if project_obj.status in [1, 4, 5]:
                    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
                    user_obj = instance.servicedeskuser
                    history = created_at + " " + "by" + " " + user_obj.user_name
                    project_obj.status = 5
                    project_obj.save()
                    project_status_change_message = {"External Update at": history}
                    AuditHistory.objects.create(
                        model_reference="project",
                        model_id=project_obj.id,
                        by_servicedesk_user=user_obj,
                        change_message=project_status_change_message,
                    )
                    if 'attachments' in serializer.data.keys():
                        user_obj = instance.servicedeskuser
                        content_type = ContentType.objects.get(app_label='projects', model='project')
                        attachment_exist = False
                        for attachment in serializer.data['attachments']:
                            document_obj = ServiceDeskAttachment.objects.filter(
                                id=attachment, uploaded_by=user_obj.user_email, can_remove=True, is_delete=False
                            ).first()
                            if document_obj:
                                attachment_obj = Attachment(
                                    organization=project_obj.organization,
                                    object_id=project_obj.id,
                                    content_type=content_type,
                                    uploaded_by=user_obj,
                                    message_document=message_obj,
                                )
                                name = document_obj.document.name.split('.')[-1]
                                random_doc_name = get_random_string(20) + "." + name
                                with default_storage.open(document_obj.document.name, 'rb') as f:
                                    attachment_obj.document_name = document_obj.document_name
                                    attachment_obj.document.save(random_doc_name, File(f))
                                    f.close()
                                attachment_obj.save()
                                document_obj.is_delete = True
                                document_obj.can_remove = False
                                document_obj.save()
                                attachment_exist = True
                                doc_uploaded_message = {"Date uploaded:": history}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_uploaded_message,
                                )
                                doc_associated_message = {"Associated Project": project_obj.name}
                                AuditHistory.objects.create(
                                    model_reference="attachment",
                                    model_id=attachment_obj.id,
                                    by_servicedesk_user=user_obj,
                                    change_message=doc_associated_message,
                                    model_name=project_obj.name,
                                )
                        if attachment_exist:
                            project_status_change_message = {"Document Uploaded at": history}
                            AuditHistory.objects.create(
                                model_reference="project",
                                model_id=project_obj.id,
                                by_servicedesk_user=user_obj,
                                change_message=project_status_change_message,
                            )
                return Response(
                    MessageListSerializer(message_obj, context={'request': request}).data,
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def submitrequest_messages(self, request, *args, **kwargs):
        """
        * To view all Message of submitted request
        ```
        * auth,request_id will be pass in query params
          eg. ?auth={'token'}
        * request_id is required(id of request)
        ```
        """
        user_token = self.request.query_params.get('auth', '').strip()
        request_id = self.request.query_params.get('request_id', '').strip()
        id = self.request.query_params.get('id__gte', '')
        if not user_token or not request_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        if not str(request_id).isdigit():
            raise Http404
        instance = get_object_or_404(queryset, pk=int(request_id))
        if instance.project:
            message_objs = ServiceDeskRequestMessage.objects.filter(
                project=instance.project, is_external_message=True, is_delete=False
            ).order_by('-id')
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageListSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageListSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        elif instance.workflow:
            message_objs = ServiceDeskRequestMessage.objects.filter(
                workflow=instance.workflow, is_external_message=True, is_delete=False
            ).order_by('-id')
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageListSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageListSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        elif instance.task:
            message_objs = (
                ServiceDeskRequestMessage.objects.filter(task=instance.task, is_external_message=True, is_delete=False)
                .filter(Q(servicedesk_request=None) | Q(servicedesk_request=instance.service_desk_request))
                .order_by('-id')
            )
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageListSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageListSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        user_token = self.request.query_params.get('auth', '').strip()
        if not user_token:
            return ServiceDeskExternalRequest.objects.none()
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        instance = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        instance.replies = 0
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            'post',
        ],
    )
    def submitrequest_delete_messages(self, request, *args, **kwargs):
        """
        * To delete message of request pass request id and message id.
        ```
        > To delete message of request pass params as below:
          { "message_id": 10}
        * "auth" will be pass as query params
        * success message would be
            "message deleted successfully" and status 200
        * invalid request will return
            "please enter valid data" and status 400
        * if message is already deleted then
            API will return "Invalid Request." and status 400
        ```
        """
        if not str(kwargs.get('pk')).isdigit() or not request.data.get('message_id'):
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user_token = self.request.query_params.get('auth', '').strip()
        if not user_token:
            return ServiceDeskExternalRequest.objects.none()
        queryset = ServiceDeskExternalRequest.objects.filter(
            servicedeskuser__access_token=user_token,
            servicedeskuser__is_expire=False,
            service_desk_request__is_delete=True,
        ).order_by('-id')
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        request_obj = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True) and str(request.data['message_id']).isdigit():
            if request_obj.project:
                message_obj = ServiceDeskRequestMessage.objects.filter(
                    id=serializer.data['message_id'],
                    project=request_obj.project,
                    is_delete=False,
                    reply_by_servicedeskuser=request_obj.servicedeskuser,
                    is_external_message=True,
                ).first()
                if message_obj:
                    message_obj.is_delete = True
                    message_obj.save()
                    return Response({'detail': 'message deleted ' 'successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
            elif request_obj.workflow:
                message_obj = ServiceDeskRequestMessage.objects.filter(
                    id=serializer.data['message_id'],
                    workflow=request_obj.workflow,
                    is_delete=False,
                    reply_by_servicedeskuser=request_obj.servicedeskuser,
                    is_external_message=True,
                ).first()
                if message_obj:
                    message_obj.is_delete = True
                    message_obj.save()
                    return Response({'detail': 'message deleted ' 'successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
            elif request_obj.task:
                message_obj = ServiceDeskRequestMessage.objects.filter(
                    id=serializer.data['message_id'],
                    task=request_obj.task,
                    is_delete=False,
                    reply_by_servicedeskuser=request_obj.servicedeskuser,
                    is_external_message=True,
                ).first()
                if message_obj:
                    message_obj.is_delete = True
                    message_obj.save()
                    return Response({'detail': 'message deleted ' 'successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeskTokenVerificationAPIView(APIView):
    """
    * API to verify servicedesk-token
    ```
    * Method  : POST
    * url     : api/servicedesk-varification/<token>/
    * Response: status code 200 if token is valid
                status code 400 if token is expire
                status code 404 if email does not exist
        ----------
        If mail sent successfully
        Success Response Code :
        ----------
            200
        Error Response Code :
        ----------
            404
    ```
    """

    permission_classes = (AllowAny,)

    def get(self, request, token):
        auth_token = token.strip()
        if ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=False).exists():
            instance = ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=False).first()
            return Response({'detail': "{}".format(instance.user_email)}, status=status.HTTP_200_OK)
        elif ServiceDeskUserInformation.objects.filter(access_token=auth_token, is_expire=True).exists():
            return Response({'detail': "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        elif not ServiceDeskUserInformation.objects.filter(access_token=auth_token).exists():
            return Response({'detail': "Not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'detail': "Not found"}, status=status.HTTP_404_NOT_FOUND)


class ReSendServiceDeskLinkAPIView(APIView):
    """
    * API to re-sent request-page link
    ```
    * Method  : POST
    * url     : api/resend-requestpage-link/<email>/
    * Response: status code 200 if email sent successfully
                status code 400 if email id does not exist
        ----------
        If mail sent successfully
        Success Response Code :
        ----------
            200
        Error Response Code :
        ----------
            404
    ```
    """

    permission_classes = (AllowAny,)

    def post(self, request, email):
        email = email.lower().strip()
        instance = ServiceDeskUserInformation.objects.filter(user_email=email).first()
        if instance:
            instance.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            # set 7 day expire date
            instance.expiration_date = timezone.now() + timedelta(7)
            instance.is_expire = False
            instance.save()
            resend_link_to_user.delay(instance)
            response = {"detail": "Email sent successfully."}
            return Response(response, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)


class ServiceDeskRequestMessageViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    API to list all the messages for task/workflow/project

    * API to view message list
    ```
    To View Message List:
        model type:would be project,workflow,task
        model_id: it would be ID of
                  project,workflow,task,attachment, servicedesk
        ex:
            api/servicedeskrequest_message/?model_type=task&model_id=30
    To View Last message of project/task/workflow
        ex:
            api/servicedeskrequest_message/
            ?model_type=project&model_id=4&id__gte={last_message_id}
    ```
    """

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        model = request.GET.get('model_type', '')
        model_id = request.GET.get('model_id', '')
        id = request.GET.get('id__gte', '')
        if not model or not model_id:
            return Response({'detail': "Invalid data"}, status=status.HTTP_406_NOT_ACCEPTABLE)
        user = request.user
        company = user.company
        queryset = None
        if model.lower() == "project":
            if company and user_permission_check(user, 'project'):
                queryset = Project.objects.filter(organization=company)
            else:
                queryset = Project.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                ).distinct('id')
            project_obj = get_object_or_404(queryset, pk=int(model_id))
            message_objs = ServiceDeskRequestMessage.objects.filter(project=project_obj, is_delete=False).order_by(
                'is_first_message', '-id'
            )
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        elif model.lower() == "task":
            if user_permission_check(user, 'task'):
                q_obj = Q()
                q_obj.add(
                    Q(is_private=True, organization=company)
                    & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                    Q.OR,
                )
                q_obj.add(Q(is_private=False, organization=company), Q.OR)
                queryset = Task.objects.filter(q_obj).distinct('id')
            else:
                queryset = Task.objects.filter(
                    Q(organization=user.company),
                    Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
                ).distinct('id')
            task_obj = get_object_or_404(queryset, pk=int(model_id))
            message_objs = ServiceDeskRequestMessage.objects.filter(task=task_obj, is_delete=False).order_by(
                'is_first_message', '-id'
            )
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        elif model.lower() == "workflow":
            if user_permission_check(user, 'workflow'):
                queryset = Workflow.objects.filter(organization=company)
            else:
                queryset = Workflow.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                ).distinct('id')
            workflow_obj = get_object_or_404(queryset, pk=int(model_id))
            message_objs = ServiceDeskRequestMessage.objects.filter(workflow=workflow_obj, is_delete=False).order_by(
                'is_first_message', '-id'
            )
            if id:
                message_objs = message_objs.filter(id__gte=id)
                context = self.paginate_queryset(message_objs)
                serializer = MessageSerializer(context, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            context = self.paginate_queryset(message_objs)
            serializer = MessageSerializer(context, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        else:
            return Response({'detail': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)


class PrivilegeReportViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    API to list Privilege report

    * API to filter Privilege report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      changed_at_after=2019-03-20&changed_at_before=2019-03-30
    > filter Report for category pass "task","project","workflow"
        eg: to filter by project, task
        pass ?category=task,project,
    > filter report by user, pass user's id in user
        eg.: user=1,2,3
    > to generate report for all users do not pass user params
    > filter report by privilege pass
        Attorney Client,Work Product, Confidential in privilege
        eg.: filter by Attorney Client,Work Product
            privilege=Attorney Client,Work Product
    ```
    """

    permission_classes = (
        UserWorkGroupPermission,
        IsAuthenticated,
    )
    filterset_class = PrivilageReportFilterSet
    filter_backends = (filters.DjangoFilterBackend,)
    http_method_names = ['get']

    def get_queryset(self):
        company = self.request.user.company
        queryset = Privilage_Change_Log.objects.filter(team_member__company=company)
        user_ids = []
        category_list = []
        privilege_list = []
        privilege_qset = []
        q_user = self.request.query_params.get('user', '')
        category = self.request.query_params.get('category', '')
        privilege = self.request.query_params.get('privilege', '')
        if category:
            [category_list.append(y) for y in category.split(',')]
        if q_user:
            [user_ids.append(int(x)) for x in q_user.split(',')]
        if privilege:
            [privilege_list.append(z) for z in privilege.split(',')]
            privilege_qsets = [Q(new_privilege__icontains=privilege_value) for privilege_value in privilege_list]
            privilege_qset = privilege_qsets.pop()
            for item in privilege_qsets:
                privilege_qset |= item
        if q_user and category and privilege:
            result_queryset = queryset.filter(
                Q(category_type__in=category_list) & Q(team_member__id__in=user_ids)
            ).filter(privilege_qset)
            return result_queryset
        elif category and privilege:
            result_queryset = queryset.filter(category_type__in=category_list).filter(privilege_qset)
            return result_queryset
        else:
            return Privilage_Change_Log.objects.none()

    def get_serializer_class(self):
        return PrivielgeSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TagReportViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list Tag report

    * API to filter Tag report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      changed_at_after=2019-03-20&changed_at_before=2019-03-30
    > filter Report for category pass "task","project","workflow"
        eg: to filter by project, task
        pass ?category=task,project,
    > filter report by tags, pass tag's id
        eg.: ?tags=1,2,3
    ```
    """

    permission_classes = (
        TagReportPermission,
        IsAuthenticated,
    )
    filterset_class = TagReportFilterSet
    filter_backends = (filters.DjangoFilterBackend,)

    def get_queryset(self):
        company = self.request.user.company
        queryset = TagChangeLog.objects.filter(tag_reference__organization=company)
        category_list = []
        tag_list = []
        category = self.request.query_params.get('category', '')
        tags = self.request.query_params.get('tags', '')
        if category:
            [category_list.append(x) for x in category.split(',')]
        if tags:
            [tag_list.append(y.upper()) for y in tags.split(',')]
        if category and tags:
            result_queryset = queryset.filter(category_type__in=category_list, tag_reference__in=tag_list)
            return result_queryset
        elif category:
            result_queryset = queryset.filter(category_type__in=category_list)
            return result_queryset
        else:
            return TagChangeLog.objects.none()

    def get_serializer_class(self):
        return TagReportSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        active = (
            queryset.values('tag_reference', 'tag_reference__tag')
            .exclude(tag_reference__isnull=True)
            .annotate(
                open_project=Count('tag_reference', filter=Q(category_type='project') & Q(completed=0)),
                open_workflow=Count('tag_reference', filter=Q(category_type='workflow') & Q(completed=0)),
                open_task=Count('tag_reference', filter=Q(category_type='task') & Q(completed=0)),
                total=Count('tag_reference', filter=Q(completed=0)),
            )
        )
        complete = (
            queryset.values('tag_reference', 'tag_reference__tag')
            .exclude(tag_reference__isnull=True)
            .annotate(
                completed_project=Count('tag_reference', filter=Q(category_type='project') & Q(new=0)),
                completed_workflow=Count('tag_reference', filter=Q(category_type='workflow') & Q(new=0)),
                completed_task=Count('tag_reference', filter=Q(category_type='task') & Q(new=0)),
                total=Count('tag_reference', filter=Q(new=0)),
            )
        )
        open_serializer = OpenTagReportListSerializer(active, many=True)
        complete_serializer = CompletedTagReportListSerializer(complete, many=True)
        result = {'active': open_serializer.data, 'complete': complete_serializer.data}
        return Response(result)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def tag_report_file_generate(self, request, pk=None):
        queryset = self.filter_queryset(self.get_queryset())
        custom_queryset = (
            queryset.values('tag_reference', 'tag_reference__tag', 'category_type')
            .exclude(tag_reference__isnull=True)
            .annotate(
                active=Count(
                    'tag_reference',
                    filter=Q(completed=0),
                ),
                complete=Count('tag_reference', filter=Q(new=0)),
            )
            .order_by('category_type')
        )
        serializer = TagReportSerializer(custom_queryset, many=True)
        return Response(serializer.data)


class GroupWorkLoadReportViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list group load report

    * API to filter group load report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      changed_at_after=2019-03-20&changed_at_before=2019-03-30
    > filter Report for category pass "task","project","workflow"
        eg: to filter by project, task
        pass ?category=task,project,
    > filter report by groups pass groups id
        eg: pass groups=1,2,3
    ```
    """

    permission_classes = (
        GroupWorkLoadReportPermission,
        IsAuthenticated,
    )
    filterset_class = GroupWorkLoadFilterSet
    filter_backends = (filters.DjangoFilterBackend,)
    http_method_names = ['get']

    def get_queryset(self):
        company = self.request.user.company
        queryset = GroupWorkLoadLog.objects.filter(work_group__organization=company)
        category_list = []
        group_list = []
        category = self.request.query_params.get('category', '')
        groups = self.request.query_params.get('groups', '')
        if category:
            [category_list.append(x) for x in category.split(',')]
        if groups:
            [group_list.append(y) for y in groups.split(',')]
        if category and groups:
            result_queryset = queryset.filter(category_type__in=category_list, work_group__in=group_list)
            return result_queryset
        elif category:
            result_queryset = queryset.filter(category_type__in=category_list)
            return result_queryset
        else:
            return GroupWorkLoadLog.objects.none()

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        active = (
            queryset.values('work_group', 'work_group__name')
            .exclude(work_group__isnull=True)
            .annotate(
                open_project=Count('work_group', filter=Q(category_type='project') & Q(completed=0)),
                open_workflow=Count('work_group', filter=Q(category_type='workflow') & Q(completed=0)),
                open_task=Count('work_group', filter=Q(category_type='task') & Q(completed=0)),
                total=Count('work_group', filter=Q(completed=0)),
            )
        )
        complete = (
            queryset.values('work_group', 'work_group__name')
            .exclude(work_group__isnull=True)
            .annotate(
                completed_project=Count('work_group', filter=Q(category_type='project') & Q(new=0)),
                completed_workflow=Count('work_group', filter=Q(category_type='workflow') & Q(new=0)),
                completed_task=Count('work_group', filter=Q(category_type='task') & Q(new=0)),
                total=Count('work_group', filter=Q(new=0)),
            )
        )
        open_serializer = OpenGroupWorkLoadReportListSerializer(active, many=True)
        complete_serializer = CompletedGroupWorkLoadReportListSerializer(complete, many=True)
        result = {'active': open_serializer.data, 'complete': complete_serializer.data}
        return Response(result)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def group_workload_file_generate(self, request, pk=None):
        queryset = self.filter_queryset(self.get_queryset())
        custom_queryset = (
            queryset.values('work_group', 'work_group__name', 'category_type')
            .exclude(work_group__isnull=True)
            .annotate(
                active=Count(
                    'work_group',
                    filter=Q(completed=0),
                ),
                complete=Count('work_group', filter=Q(new=0)),
            )
            .order_by('category_type')
        )
        serializer = GroupWorkLoadLogReportSerializer(custom_queryset, many=True)
        return Response(serializer.data)


class TeamMemberWorkLoadReportViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list team member workload report

    * API to filter team member workload report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      changed_at_after=2019-03-20&changed_at_before=2019-03-30
    > filter report by team member pass id of users
        eg.: ?users=1,2,3
    > filter report by all team member do not pass user's id

    To sort Request by any field pass that field name in ordering
    Sorting fields: 'project','workflow', 'task', 'total',
    e.g : ascending by project > ordering=project
         descending by project > ordering=-project
    ```
    """

    permission_classes = (
        TeamMemberWorkLoadPermission,
        IsAuthenticated,
    )
    filterset_class = TeamMemberWorkLoadFilterSet
    filter_backends = (
        filters.DjangoFilterBackend,
        OrderingFilter,
    )
    ordering_fields = ['team_member', 'project', 'workflow', 'task', 'total']

    def get_queryset(self):
        company = self.request.user.company
        queryset = TeamMemberWorkLoadLog.objects.filter(team_member__company=company)
        user_list = []
        users = self.request.query_params.get('users', '')
        if users:
            [user_list.append(y) for y in users.split(',')]
        if users:
            result_queryset = queryset.filter(team_member__in=user_list)
            return result_queryset
        else:
            return TeamMemberWorkLoadLog.objects.all()

    def get_serializer_class(self):
        return TeamMemberWorkLoadReportListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = (
            queryset.exclude(Q(team_member__isnull=True) | Q(team_member__is_delete=True))
            .values('team_member')
            .annotate(
                project=Count('team_member', filter=Q(category_type='project')),
                workflow=Count('team_member', filter=Q(category_type='workflow')),
                task=Count('team_member', filter=Q(category_type='task')),
                total=Count('team_member'),
            )
        )
        serializer = TeamMemberWorkLoadReportListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def team_member_workload_file_generate(self, request):
        """
        >API to get Team Member WorkLoad file generate.
        ```
        * Response will return json object of
            *team_member*, *category_type* & *total_count*
        ```
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = (
            queryset.exclude(Q(team_member__isnull=True) | Q(team_member__is_delete=True))
            .values('team_member', 'category_type')
            .annotate(
                total_count=Count('team_member', filter=Q(new=1)),
            )
        )
        serializer = TeamMemberWorkLoadReportFileSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EfficiencyReportViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list team member efficiency report

    * API to filter team member efficiency report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      from_date=2019-03-20&to_date=2019-03-30
      (required else it will return none)
    > filter report by team member pass id of users
        eg.: ?users=1,2,3
    > filter report by all team member do not pass user's id
    ```
    """

    permission_classes = (
        EfficiencyPermission,
        IsAuthenticated,
    )
    filter_backends = (filters.DjangoFilterBackend,)
    http_method_names = ['get']

    def get_queryset(self):
        company = self.request.user.company
        queryset = CompletionLog.objects.filter(team_member__company=company)
        user_list = []
        users = self.request.query_params.get('users', '')
        from_date = self.request.query_params.get('from_date', '')
        to_date = self.request.query_params.get('to_date', '')
        if users:
            [user_list.append(y) for y in users.split(',')]
        if users and from_date and to_date:
            result_queryset = queryset.filter(
                team_member__in=user_list,
                created_on__range=[from_date, to_date],
                completed_on__range=[from_date, to_date],
            )
            return result_queryset
        elif from_date and to_date:
            result_queryset = queryset.filter(
                created_on__range=[from_date, to_date], completed_on__range=[from_date, to_date]
            )
            return result_queryset
        else:
            return CompletionLog.objects.none()

    def get_serializer_class(self):
        return EfficiencyReportSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        work_time = ExpressionWrapper(F('completion_time') * 8, output_field=fields.DurationField())
        queryset = (
            queryset.exclude(Q(team_member__isnull=True) | Q(team_member__is_delete=True))
            .annotate(work_time=work_time)
            .values('team_member')
            .annotate(
                project_avg=Coalesce(Avg('work_time', filter=Q(project__isnull=False)), 0),
                workflow_avg=Coalesce(Avg('work_time', filter=Q(workflow__isnull=False)), 0),
                task_avg=Coalesce(Avg('work_time', filter=Q(task__isnull=False)), 0),
            )
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def efficiency_file_generate(self, request):
        """
        >API to get efficiency statistic data for file generate.
        ```
        * Response will return json object of
            *created_on*, *completed_on*, *completion_time*,
            *category_type*, *name*, *team_member*
        ```
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = EfficiencyReportFileSerializer(queryset, many=True)
        return Response(serializer.data)


class ProductivityReportViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list team member/ group productivity report
    * API to filter team member/group productivity report
    ```
    filter report
    - To filter report by date range:
    > Report created between 20 march to 30 march
      created_on_after=2019-03-20&created_on_before=2019-03-30
    > filter Report for category pass "task","project","workflow"
        (required otherwise it will return 404)
        eg: to filter by project, task
        pass ?category=task,project,
    > filter report by team member pass id of users
        eg.: ?users=1,2,3
    > filter report by all team member do not pass user ids
    > filter report by group pass id of groups
        eg.: ?groups=1,2,3
    > filter report by all groups do not pass group ids
    To sort Request by any field pass that field name in ordering
    Sorting fields: 'active','complete',
    e.g : ascending by active > ordering=active
         descending by active > ordering=-active
    ```
    """

    permission_classes = (
        WorkProductivityLogPermission,
        IsAuthenticated,
    )
    filterset_class = WorkProductivityLogFilterSet
    filter_backends = (filters.DjangoFilterBackend,)
    ordering_fields = ['active', 'complete']
    http_method_names = ['get']

    def get_queryset(self):
        company = self.request.user.company
        queryset = WorkProductivityLog.objects.filter(
            Q(team_member__company=company) | Q(work_group__organization=company)
        )
        category_list = []
        user_list = []
        group_list = []
        category = self.request.query_params.get('category', '')
        users = self.request.query_params.get('users', '')
        groups = self.request.query_params.get('groups', '')
        if category:
            [category_list.append(x) for x in category.split(',')]
        if users:
            [user_list.append(y) for y in users.split(',')]
        if groups:
            [group_list.append(z) for z in groups.split(',')]
        if category and users and groups:
            result_queryset = queryset.filter(
                Q(category_type__in=category_list), Q(team_member__in=user_list) | Q(work_group__in=group_list)
            )
            return result_queryset
        elif category and users:
            result_queryset = queryset.filter(category_type__in=category_list, team_member__in=user_list)
            return result_queryset
        elif category and groups:
            result_queryset = queryset.filter(category_type__in=category_list, work_group__in=group_list)
            return result_queryset
        elif category:
            result_queryset = queryset.filter(category_type__in=category_list)
            return result_queryset
        else:
            return WorkProductivityLog.objects.none()

    def get_serializer_class(self):
        return ProductivityReportSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = (
            queryset.exclude(Q(team_member__isnull=True) | Q(team_member__is_delete=True))
            .values('team_member')
            .annotate(
                active=Count('team_member', filter=Q(completed=0)),
                complete=Count('team_member', filter=Q(new=0)),
            )
        )
        serializer = ProductivityReportListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def productivity_file_generate(self, request):
        """
        > API to get productivity statistic data for
          file generate.
        ```
        * Response will return json object of *active* & *completed*
        ```
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = (
            queryset.values('team_member', 'category_type')
            .exclude(Q(team_member__isnull=True) | Q(team_member__is_delete=True))
            .annotate(
                active=Count('team_member', filter=Q(completed=0)),
                completed=Count('team_member', filter=Q(new=0)),
            )
            .order_by('category_type')
        )
        serializer = ProductivityReportFileSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def productivity_graph_generate(self, request):
        """
        >API to get productivity statistic data for graph generate.
        ```
        * Response will return *project*, *workflow*, *task* count
        based on year and month

        ```
        ```
        filter graph by status show
        - by default it will return New & Completed(PWT)
        values : 1:New(PWT), 2:Completed(PWT),
        > display new data graph only :show_by=1
        ```
        """
        show_by = request.query_params.get('show_by', '')
        if show_by:
            show_by = int(show_by)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.exclude(created_on__isnull=True).values('created_on')
        if show_by == 1:
            queryset = (
                queryset.annotate(
                    project=Count('category_type', filter=Q(completed=0) & Q(category_type='project')),
                    workflow=Count('category_type', filter=Q(completed=0) & Q(category_type='workflow')),
                    task=Count('category_type', filter=Q(completed=0) & Q(category_type='task')),
                )
                .values('created_on', 'project', 'workflow', 'task')
                .order_by('created_on')
            )
        elif show_by == 2:
            queryset = (
                queryset.annotate(
                    project=Count('category_type', filter=Q(new=0) & Q(category_type='project')),
                    workflow=Count('category_type', filter=Q(new=0) & Q(category_type='workflow')),
                    task=Count('category_type', filter=Q(new=0) & Q(category_type='task')),
                )
                .values('created_on', 'project', 'workflow', 'task')
                .order_by('created_on')
            )
        else:
            queryset = (
                queryset.annotate(
                    project=Count('category_type', filter=Q(category_type='project')),
                    workflow=Count('category_type', filter=Q(category_type='workflow')),
                    task=Count('category_type', filter=Q(category_type='task')),
                )
                .values('created_on', 'project', 'workflow', 'task')
                .order_by('created_on')
            )
        serializer = ProductivityReporGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardStatisticsViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group = user.group
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='task_task-view-all'
        ).exists():
            q_obj = Q()
            q_obj.add(
                Q(is_private=True, organization=company)
                & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
                Q.OR,
            )
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = Task.objects.filter(q_obj).distinct('id')
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='task_task-view'
        ).exists():
            queryset = Task.objects.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        else:
            queryset = Task.objects.none()
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        return queryset

    def get_serializer_class(self):
        return None

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def assigned_task(self, request):
        """
        >API to get dashboard pie chart(assign task) statistic data.
        ```
        * total number of task where assigned to
          me only *my_task*
        * total number of task where assigned to
          groups of which I'm a member *our_task*
        * total number of task where assigned to
          other people in groups I'm assigned to *their_task*
        ```
        """
        user = request.user
        queryset = self.get_queryset().values_list('id', flat=True).distinct()
        # get my all workgorup
        my_work_group = WorkGroup.objects.filter(group_members=user).distinct()
        # get my all workgroup member
        my_group_member = (
            WorkGroup.objects.filter(id__in=my_work_group.values_list('id', flat=True))
            .values_list('group_members__id', flat=True)
            .distinct()
        )
        my_task = Task.objects.filter(id__in=queryset, assigned_to=user).count()
        our_task = (
            Task.objects.filter(id__in=queryset, assigned_to_group__in=my_work_group).exclude(assigned_to=user).count()
        )
        their_task = (
            Task.objects.filter(id__in=queryset, assigned_to__id__in=my_group_member).exclude(assigned_to=user).count()
        )
        detail = {
            'my_task': my_task,
            'our_task': our_task,
            'their_task': their_task,
        }
        return Response({'detail': detail}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=[
            'get',
        ],
    )
    def upcoming_week(self, request):
        """
        >API to get dashboard Bar Chart(Upcoming Week)
        statistic data.
        ```
        * list of upcoming task based on date with
          count *upcoming_task*
        * list of upcoming workflow based on date with
          count *upcoming_workflow*
        * list of upcoming project based on date with
          count *upcoming_project*
        ```
        """
        offset_time = request.GET.get('offset_time')
        if not offset_time:
            return Response({'detail': "offset_time is required field"}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        task_queryset = self.get_queryset().exclude(status__in=[3, 4])
        company = user.company
        group = user.group
        # calculate upcoming week
        start_of_week = (
            datetime.datetime.utcnow().replace(hour=0, minute=0, second=0)
            + timedelta(1)
            - timedelta(minutes=int(offset_time))
        )
        # get permitted project object
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='project_project-view-all'
        ).exists():
            project_queryset = Project.objects.filter(organization=company).exclude(status__in=[2, 3])
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='project_project-view'
        ).exists():
            project_queryset = (
                Project.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
                .exclude(status__in=[2, 3])
                .distinct()
            )
        else:
            project_queryset = Project.objects.none()
        # get permitted workflow object
        if GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view-all'
        ).exists():
            workflow_queryset = Workflow.objects.filter(organization=company).exclude(status__in=[2, 3])
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='workflow_workflow-view'
        ).exists():
            workflow_queryset = (
                Workflow.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
                .exclude(status__in=[2, 3])
                .distinct()
            )
        else:
            workflow_queryset = Workflow.objects.none()
        # get all upcoming task, workflow and project
        response_data = []
        for day in range(0, 7):
            response_data.append(
                {
                    str((start_of_week + timedelta(day) + timedelta(minutes=int(offset_time))).date()): {
                        'project': project_queryset.filter(
                            due_date__range=[
                                (start_of_week + timedelta(day)),
                                start_of_week + timedelta(day) + timedelta(1),
                            ]
                        ).count(),
                        'workflow': workflow_queryset.filter(
                            due_date__range=[
                                (start_of_week + timedelta(day)),
                                start_of_week + timedelta(day) + timedelta(1),
                            ]
                        ).count(),
                        'task': task_queryset.filter(
                            due_date__range=[
                                (start_of_week + timedelta(day)),
                                start_of_week + timedelta(day) + timedelta(1),
                            ]
                        ).count(),
                    }
                }
            )
        return Response({'detail': response_data}, status=status.HTTP_200_OK)


class ShareDocumentViewSet(viewsets.GenericViewSet):
    """
    share_document:
    * API to share document of private task
    ```
    > document_id, email are required
    > pass document id in 'document_id' and
                          list of emails in 'email'
    > eg:
        {
        "document_id":10,
        "email":["codal@codal.com","codal.1@codal.com"]
        }
    ```
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = ShareDocumentSerializer

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group = user.group
        queryset = Task.objects.none()
        if GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug__in=['task_task-view-all', 'task_task-view'],
            has_permission=True,
        ).exists():
            queryset = Task.objects.filter(
                Q(organization=user.company, is_private=True),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        docs_queryset = Attachment.objects.filter(
            organization=company, is_delete=False, task_id__in=queryset.values_list('id', flat=True)[::1]
        )
        return docs_queryset

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def share_document(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            document_obj = get_object_or_404(queryset, pk=int(serializer.data['document_id']))
            share_document_to_user.delay(document_obj, serializer.data.get('email'), request.user)
            return Response({'detail': 'Document shared successfully'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CeleryDrainViewSet(ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (AllowAny,)

    def get_queryset(self):
        return None

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        access_token = self.request.query_params.get('api_key', None)
        if not access_token:
            return Response({"detail": "Invalid request."}, status=status.HTTP_403_FORBIDDEN)
        if access_token.strip() != settings.CELERY_KEY:
            return Response({"detail": "Invalid API key."}, status=status.HTTP_403_FORBIDDEN)
        from nmbl.celery import app

        woker_name = os.getenv('MY_POD_NAME', socket.gethostname())
        inspector = app.control.inspect(destination=['celery@{}'.format(woker_name)])
        controller = app.control
        active_queues = inspector.active_queues()
        all_queues = set()
        for worker, queues in active_queues.items():
            for queue in queues:
                all_queues.add(queue['name'])
        for queue in all_queues:
            controller.cancel_consumer(queue, destination=['celery@{}'.format(woker_name)])
        done = False
        while not done:
            active_count = 0
            active = inspector.active()
            active_count = sum(map(lambda l: len(l), active.values()))
            print("Active Tasks {}".format(active_count))
            done = active_count == 0
            if not done:
                print("Waiting for 60 seconds")
                time.sleep(60)  # wait a minute between checks
        return Response({"detail": "success."}, status=status.HTTP_200_OK)
