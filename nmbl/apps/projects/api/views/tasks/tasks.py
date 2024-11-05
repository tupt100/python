import uuid
from datetime import timedelta

from authentication.models import GroupAndPermission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch, Q
from django.http import Http404
from django.utils import timezone
from django_filters import rest_framework as filters
from projects.api.serializers import TaskCreateSerializer, TaskUpdateSerializer
from projects.filters import TaskFilterSet
from projects.helpers import (
    AuditHistoryCreate,
    document_associate_history,
    send_notification_to_servicedeskuser,
    task_attachment_uploaded_notification,
    task_new_internal_message_notification,
    task_new_message_notification,
    user_permission_check,
)
from projects.models import (
    Attachment,
    Project,
    ServiceDeskExternalCCUser,
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskRequestMessage,
    ServiceDeskUserInformation,
    Task,
    TaskRank,
    Workflow,
)
from projects.permissions import CustomPermission
from projects.serializers import (
    AssociateNewRequestSerializer,
    ItemTitleRenameSerializer,
    MessageDeleteSerializer,
    MessageSerializer,
    TaskDetailSerializer,
    TaskMessageSerializer,
    TaskRankDetailSerializer,
    TaskRankListSerializer,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet


class TaskViewSet(ModelViewSet):
    """
    list:
    API to list all Task in my organisation

    * Filter task by importance
    ```
    Importance values ==> 1: Low, 2: Med, 3: High
    To filter task by High > importance=3
    To filter task by High & Low > importance=1,3
    ```
    * API to Sort task by rank
    ```
    Sort by rank in ascending order : order_by_rank=rank
    Sort by rank in descending order : order_by_rank=-rank
    ```

    * Filter task by status
    ```
    Status values ==>
        1: New, 2: In-Progress, 3: Completed,
        4: Archived, 5: External Request
    To filter task by New > status=1
    To filter task by New & Completed > status=1,3
    ```

    * Filter task by workflow
    ```
    To filter task by workflow > workflow=1
    To filter task by workflow> workflow=1,2
    ```

    * Filter task by project
    ```
    To filter task by project > project=1
    To filter task by project> project=1,3
    ```

    * Filter task by assigned
    ```
    To filter task by assigned > assigned_to=1
    ```

    * Filter Task by date range
    ```
    To filter task by created date,due_date range:
    > For task created between 20 march to 30 march
      task__created_at_after=2019-03-20&created_at_before=2019-03-30
    > For task due date between 20 march to 30 march
      task__due_date_after=2019-03-20&due_date_before=2019-03-30

    To filter task using text: `today, yesterday, week, month, year`
    > For task created today
      task__created_at_txt=today
    > For task due date today
      task__due_date_txt=today
    > For task due date null
      due_date__isnull=true
    ```

    * Sort Task by fields
    ```
    To sort task by any field pass that field name in ordering
    Sorting fields: 'task__name', 'task__assigned_to', 'task__status',
                    'task__due_date', 'task__importance',
                    'task__assigned_by','rank'
    e.g : ascending by name > ordering=task__name
         descending by name > ordering=-task__name

    create:
    API to create Task in my organisation:

    * create a task base on task template
    ```
    For create a task base on task template you must send all fields + `task_template_id` + `custom_fields_value`
    `task_template_id` --> primary key of `task template`
    `custom_fields_value` dictionary base on `pk` of `custom_field`  --> {"pk": "value", "pk": "value"}
    ```

    partial_update:
    API to update task details you need to pass that task id

    * change due date for a task
    ```
    To update due date pass `due_date` or `start_date` as below example:
        { "due_date": "2020-01-01T11:40:01+05:30" }
    ```

    * change custom fields for a task
    ```
    To update custom fields pass `custom_fields_value` with `pk` and value for custom fields (send all custom fields
     related to task template is required, if you dont send
     it's replace with default value or raise an error) as below example:
        { "custom_fields_value": {"3": 3, "4": "Text", "5": "2020-12-12T00:00"}}
    ```

    * add documents in task
    ```
    To add documents in task pass document's ids as below example:
        attachments=[1, 2]
    ```

    * add tags in task
    ```
    To add tags in task pass tag's ids as below example:
        task_tags=["abc","xyz"]
    ```
    """

    model = Task
    permission_classes = (CustomPermission,)
    filterset_class = TaskFilterSet
    filter_backends = (
        filters.DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )
    search_fields = [
        'task__name',
    ]
    ordering_fields = ['task__name', 'task__assigned_to', 'task__status', 'task__due_date', 'rank']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group = user.group
        if user_permission_check(user, 'task'):
            q_obj = Q()
            q_obj.add(
                Q(task__is_private=True, task__organization=company, user=user)
                & Q(
                    Q(task__assigned_to=user)
                    | Q(task__created_by=user)
                    | Q(task__assigned_to_group__group_members=user)
                ),
                Q.OR,
            )
            q_obj.add(Q(task__is_private=False, task__organization=company, user=user), Q.OR)
            queryset = TaskRank.objects.filter(q_obj).distinct()
        else:
            queryset = TaskRank.objects.filter(
                Q(task__organization=company, user=user),
                Q(task__assigned_to=user) | Q(task__created_by=user) | Q(task__assigned_to_group__group_members=user),
            ).distinct()
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(task__status__in=[3, 4])
        task_type = self.request.query_params.get('type', None)
        if task_type:
            if task_type.lower() == "active":
                queryset = queryset.exclude(task__status__in=[3, 4])
            elif task_type.lower() == "archived":
                queryset = queryset.filter(task__status__in=[3, 4])
            else:
                queryset = TaskRank.objects.none()
        user_ids = []
        group_ids = []
        exclude_request_task = True if self.request.query_params.get("exclude_request_task") == 'true' else False
        if exclude_request_task:
            attached_task = list(
                ServiceDeskExternalRequest.objects.exclude(task=None).values_list('task__id', flat=True)
            )
            result_queryset = queryset.exclude(Q(task__id__in=attached_task) | Q(task__status__in=[3, 4])).distinct()
            return result_queryset
        q_user = self.request.query_params.get('user', '')
        if q_user:
            [user_ids.append(int(x)) for x in q_user.split(',')]
        q_group_member = self.request.query_params.get('group_member', '')
        q_group = self.request.query_params.get('group', '')
        if q_group:
            [group_ids.append(int(x)) for x in q_group.split(',')]
        if q_user and q_group_member and not q_group:
            result_queryset = queryset.filter(
                Q(task__assigned_to__id__in=user_ids) | Q(task__assigned_to_group__group_members__id__in=user_ids)
            ).distinct()
            return result_queryset
        elif q_user and q_group_member and q_group:
            result_queryset = queryset.filter(
                Q(task__assigned_to__id__in=user_ids)
                | Q(task__assigned_to_group__group_members__id__in=user_ids)
                | Q(task__assigned_to_group__id__in=group_ids)
            ).distinct()
            return result_queryset
        elif q_group and not (q_user and q_group_member):
            result_queryset = queryset.filter(Q(task__assigned_to_group__id__in=group_ids)).distinct()
            return result_queryset
        else:
            pass
        queryset = queryset.prefetch_related(Prefetch('task__task_attachment', queryset=Attachment.objects.active()))
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        elif self.action == 'retrieve':
            return TaskRankDetailSerializer
        elif self.action == 'partial_update':
            return TaskUpdateSerializer
        elif self.action == 'rename_title':
            return ItemTitleRenameSerializer
        elif self.action == 'request_associate_to_task':
            return AssociateNewRequestSerializer
        elif self.action == 'task_add_messages':
            return TaskMessageSerializer
        elif self.action == 'task_delete_messages':
            return MessageDeleteSerializer
        return TaskRankListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = TaskRankListSerializer(context, many=True, context={'request': request, "q_set": queryset})
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                'detail': 'Task created successfully',
                'task_id': serializer.instance.pk,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        user = request.user
        company = user.company
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
        instance = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        # if instance.status in [3, '3', 4, '4']:
        #     return Response({"detail": "You cannot update
        #                           archive/completed task."},
        #                     status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        # if instance.is_assignee_changed:
        #     create_taskrank(instance)
        #     instance.is_assignee_changed = False
        #     instance.save()
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        return Response(TaskDetailSerializer(instance, context={'request': request}).data)

    def retrieve(self, request, *args, **kwargs):
        if not str(kwargs.get('pk')).isdigit():
            raise Http404
        instance = get_object_or_404(self.get_queryset(), task_id=int(kwargs.get('pk')))
        AuditHistoryCreate("task", instance.task_id, self.request.user, "Viewed By")
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
        Extra action to rename/update title of a Task.

        * to rename title for a Task, Task-Id need to be passed.

        ```
        To update/rename title pass `name` as below:
        { "name": "updating task title" }
        ```
        """
        user = request.user
        company = user.company
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
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [3, 4]:
            return Response({'detail': 'Invalid Request.'}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            instance.name = serializer.data['name']
            instance.save()
            # create record in Audit History
            AuditHistoryCreate("task", instance.id, self.request.user, "Renamed by")
            return Response({'detail': 'Task title updated.'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'patch',
        ],
    )
    def request_associate_to_task(self, request, pk=None):
        """
        * To Associate Request to task
        ```
        * user_name is required
        * user_email is required
        * attachments are optional
            (pass key if attachments are available)
        ```
        """
        if not str(request.data['user_email']) or not str(request.data['user_email']):
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        company = user.company
        group = user.group
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
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        instance = get_object_or_404(queryset, pk=pk)
        if instance.status in [3, 4]:
            return Response({'detail': 'Invalid Request.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user_email = serializer.data['user_email'].lower().strip()
            if ServiceDeskExternalRequest.objects.filter(
                servicedeskuser__user_email=user_email, task=instance
            ).exists():
                return Response(
                    {'detail': 'External request with ' 'this user already exists.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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
            # request_submit_notification.delay(request_obj, user,
            # instance, "task")
            external_request_obj = ServiceDeskExternalRequest.objects.create(
                task=instance,
                servicedeskuser=servicedesk_user,
                created_by=request.user,
                service_desk_request=request_obj,
            )
            message_obj = ServiceDeskRequestMessage.objects.create(
                created_by_user=user,
                task=instance,
                message=description,
                is_external_message=True,
                servicedesk_request=request_obj,
            )
            if serializer.data.get('cc'):
                [
                    ServiceDeskExternalCCUser.objects.create(
                        email=email.lower().strip(),
                        message=message_obj,
                        external_request=external_request_obj,
                        created_by=user,
                    )
                    for email in serializer.data.get('cc')
                ]
            if 'attachments' in serializer.data.keys():
                content_type = ContentType.objects.get(app_label='projects', model='task')
                # Document Uploaded to New Task
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
                            "attachment", attachment_obj.id, instance.name, "Associated Task", user
                        )
                if attachment_exist:
                    AuditHistoryCreate("task", instance.id, user, "Document Uploaded at")
                    if instance.created_by == instance.assigned_to:
                        task_attachment_uploaded_notification(instance, instance.created_by)
                    else:
                        task_attachment_uploaded_notification(instance, instance.created_by)
                        task_attachment_uploaded_notification(instance, instance.assigned_to)
                    if instance.assigned_to_group:
                        for task_group in instance.assigned_to_group.all():
                            [
                                task_attachment_uploaded_notification(instance, group_member)
                                for group_member in task_group.group_members.all()
                            ]
            send_notification_to_servicedeskuser.delay(external_request_obj, message_obj, True)
            return Response({'detail': 'Task linked to request ' 'successfully!.'}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=[
            'post',
        ],
    )
    def task_add_messages(self, request, *args, **kwargs):
        """
        * To add new message
        ```
        * pass task id,message,is_external_message,
               is_internal_message,attachments
        * attachments are optional pass attachment ids if exists
        * if message is internal then pass "is_internal_message=True"
          else False
        * if message is external then pass "is_external_message=True"
          else False
        * do pass like
            eg. {"is_internal_message=True" ,"is_external_message=True"} or
            {"is_internal_message=False" ,"is_external_message=False"} at a
            same time
        * if task has external request then only pass
        ```
        """
        user = request.user
        company = user.company
        group = user.group
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
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.filter(status__in=[3, 4])
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            task_obj = get_object_or_404(queryset, pk=int(serializer.data['task']))
            if serializer.data['is_internal_message']:
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'], task=task_obj, created_by_user=user, is_internal_message=True
                )
                if 'attachments' in serializer.data.keys() and task_obj.status not in [3, 4]:
                    content_type = ContentType.objects.get(app_label='projects', model='task')
                    # Document Uploaded to New Task
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
                            attachment_obj.object_id = task_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, task_obj.name, "Associated Task", user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("task", task_obj.id, user, "Document Uploaded at")
                # send new message notification to assigned user
                task_new_internal_message_notification.delay(task_obj, message_obj)
                return Response(
                    MessageSerializer(message_obj, context={'request': request}).data, status=status.HTTP_201_CREATED
                )
            elif serializer.data['is_external_message']:
                external_request_obj = ServiceDeskExternalRequest.objects.filter(
                    task=task_obj, service_desk_request_id=serializer.data['request_id']
                ).first()
                if not external_request_obj:
                    return Response(
                        {'detail': 'External request ' 'does not exists.'}, status=status.HTTP_400_BAD_REQUEST
                    )
                main_request = external_request_obj.service_desk_request
                message_obj = ServiceDeskRequestMessage.objects.create(
                    message=serializer.data['message'],
                    task=task_obj,
                    created_by_user=user,
                    is_external_message=True,
                    servicedesk_request=main_request,
                )
                external_request_obj.replies += 1
                external_request_obj.save()
                if serializer.data.get('cc'):
                    [
                        ServiceDeskExternalCCUser.objects.create(
                            email=email.lower().strip(),
                            message=message_obj,
                            external_request=external_request_obj,
                            created_by=user,
                        )
                        for email in serializer.data.get('cc')
                    ]
                if 'attachments' in serializer.data.keys() and task_obj.status not in [3, 4]:
                    content_type = ContentType.objects.get(app_label='projects', model='task')
                    # Document Uploaded to New Task
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
                            attachment_obj.object_id = task_obj.id
                            attachment_obj.message_document = message_obj
                            attachment_obj.save()
                            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                            document_associate_history(
                                "attachment", attachment_obj.id, task_obj.name, "Associated Task", user
                            )
                    if attachment_exist:
                        AuditHistoryCreate("task", task_obj.id, user, "Document Uploaded at")
                # new message notification to service desk user
                task_new_message_notification.delay(message_obj, task_obj, user)
                return Response(
                    MessageSerializer(message_obj, context={'request': request}).data, status=status.HTTP_201_CREATED
                )
            else:
                return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'post',
        ],
    )
    def task_delete_messages(self, request, *args, **kwargs):
        """
        * To delete message of Task pass Task id and message id.

        ```
        > To update/rename title pass `name` as below:
          { "message_id": 10}
        * success message would be "message deleted successfully"
            and status 200
        * invalid request will return "please enter valid data"
            and status 400
        * if message is already deleted then API will
            return "This message is already deleted." and
            status 400
        ```
        """
        if not str(kwargs.get('pk')).isdigit() or not str(request.data['message_id']).isdigit():
            return Response({'detail': 'please enter valid data.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        company = user.company
        group = user.group
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
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.filter(status__in=[3, 4])
        task_obj = get_object_or_404(queryset, pk=int(kwargs.get('pk')))
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            message_obj = ServiceDeskRequestMessage.objects.filter(
                id=serializer.data['message_id'], task=task_obj, is_delete=False, created_by_user=user
            ).first()
            if message_obj:
                message_obj.is_delete = True
                message_obj.save()
                return Response({'detail': 'message deleted ' 'successfully.'}, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'This message is already ' 'deleted.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=[
            'get',
        ],
    )
    def task_details_statistic(self, request, pk=None):
        """
        > API will return following detail for selected task

        > if task have workflow and it is accessable for user
          then return below details
        * name of the workflow as *workflow*
        * id of the workflow as *workflow_id*
        * importance of the workflow as *workflow_importance*
        * total number of task in the workflow as *workflow_total_task*

        > if workflow have project and it is accessable for
          user then return below details
        * name of the project as *project_name*
        * id of the project as *project_id*
        * importance of the project as *project_importance*
        * total number of workflow in the project as *project_total_workflow*
        ```
        """
        user = request.user
        group = user.group
        company = user.company
        detail = {
            'workflow': None,
            'workflow_id': None,
            'workflow_importance': None,
            'workflow_total_task': None,
            'project_name': None,
            'project_importance': None,
            'project_id': None,
            'project_total_workflow': None,
        }
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
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            queryset = queryset.exclude(status__in=[3, 4])
        instance = get_object_or_404(queryset, pk=pk)
        if instance.workflow:
            workflow = instance.workflow
            # get all the accessable workflow queryset as
            # "workflow_queryset" and make dublicate queryset
            # list of all id
            if GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                has_permission=True,
                permission__slug='workflow_workflow-view-all',
            ).exists():
                workflow_queryset = Workflow.objects.filter(organization=company)
                if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='workflow',
                    permission__slug='workflow_view-archived',
                    has_permission=True,
                ).exists():
                    workflow_queryset = workflow_queryset.exclude(status__in=[2, 3])
                workflow_ids = workflow_queryset.values_list("id", flat=True).distinct()
            elif GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                has_permission=True,
                permission__slug='workflow_workflow-view',
            ).exists():
                workflow_queryset = Workflow.objects.filter(
                    Q(organization=company),
                    Q(owner=user)
                    | Q(assigned_to_users=user)
                    | Q(created_by=user)
                    | Q(assigned_to_group__group_members=user),
                )
                if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='workflow',
                    permission__slug='workflow_view-archived',
                    has_permission=True,
                ).exists():
                    workflow_queryset = workflow_queryset.exclude(status__in=[2, 3])
                workflow_ids = workflow_queryset.values_list("id", flat=True).distinct()
            else:
                workflow_ids = []
            if not workflow_ids:
                return Response({'detail': 'Invalid Request'}, status=status.HTTP_400_BAD_REQUEST)
            # check task workflow have accessible and get
            # all task of the workflow
            if workflow.id in workflow_ids:
                total_task_of_workflow = (
                    queryset.filter(workflow=workflow, organization=company).values_list('id', flat=True).distinct()
                )
                detail['workflow'] = workflow.name
                detail['workflow_id'] = workflow.id
                detail['workflow_importance'] = workflow.importance
                detail['workflow_total_task'] = total_task_of_workflow.count()
                if not workflow.project:
                    return Response({'detail': detail}, status=status.HTTP_200_OK)
                else:
                    # get all the accessible project queryset
                    # as "project_queryset" and make duplicate
                    # queryset list of all id
                    if GroupAndPermission.objects.filter(
                        group=group,
                        company=company,
                        permission__permission_category='project',
                        has_permission=True,
                        permission__slug='project_project-view-all',
                    ).exists():
                        project_queryset = Project.objects.filter(organization=company)
                        if not GroupAndPermission.objects.filter(
                            group=group,
                            company=company,
                            permission__permission_category='project',
                            permission__slug='project_view-archived',
                            has_permission=True,
                        ).exists():
                            project_queryset = project_queryset.exclude(status__in=[2, 3])
                        project_ids = project_queryset.values_list('id', flat=True).distinct()
                    elif GroupAndPermission.objects.filter(
                        group=group,
                        company=company,
                        permission__permission_category='project',
                        has_permission=True,
                        permission__slug='project_project-view',
                    ).exists():
                        project_queryset = Project.objects.filter(
                            Q(organization=company),
                            Q(owner=user)
                            | Q(assigned_to_users=user)
                            | Q(created_by=user)
                            | Q(assigned_to_group__group_members=user),
                        )
                        if not GroupAndPermission.objects.filter(
                            group=group,
                            company=company,
                            permission__permission_category='project',
                            permission__slug='project_view-archived',
                            has_permission=True,
                        ).exists():
                            project_queryset = project_queryset.exclude(status__in=[2, 3])
                        project_ids = project_queryset.values_list('id', flat=True).distinct()
                    else:
                        project_ids = []
                    # check user have access to task of workflow of project
                    if not project_ids or workflow.project.id not in project_ids:
                        return Response({'detail': detail}, status=status.HTTP_200_OK)
                    total_project_of_workflow = (
                        workflow_queryset.filter(project=workflow.project).values_list('id', flat=True).distinct()
                    )
                    detail['project_name'] = workflow.project.name
                    detail['project_importance'] = workflow.project.importance
                    detail['project_id'] = workflow.project.id
                    detail['project_total_workflow'] = total_project_of_workflow.count()
            return Response({'detail': detail}, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Invalid Request'}, status=status.HTTP_400_BAD_REQUEST)
