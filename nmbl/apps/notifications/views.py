from authentication.models import GroupAndPermission
from authentication.models import User
from authentication.permissions import PermissionManagerPermission
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from projects.helpers import task_ping_notification, \
    AuditHistoryCreate, user_permission_check
from projects.models import Task
from rest_framework import viewsets, status
from rest_framework.authentication import TokenAuthentication, \
    SessionAuthentication
from rest_framework.decorators import list_route
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import NotificationFilterSet
from .models import Notification, UserNotificationSetting, \
    NotificationType, NOTIFICATION_CATEGORY_CHOICES
from .permissions import MyNotificationPermission, \
    CompanyUserNotificationPermission
from .serializers import (NotificationSerializer, AskTaskUpdateSerializer,
                          UserNotificationSettingSerializer,
                          CompanyUserNotificationSerializer)


class NotificationViewSet(viewsets.ModelViewSet):
    """
        Method  : GET
        url     : notifications/api/
        Response: List of all notification for particular users
    * API to Sort Notification by status
    ```
    > Sort by status(new/unread) pass ?ordering=-status
    > Sort by status(read) pass ?ordering=status
    > To sort notification in ascending order by
        created date pass ?ordering=created_at
    > To sort notification in descending
        order by created date pass ?ordering=-created_at
    > To filter unread notification pass status=1
    > To filter read notification pass status=2
    ```
    """
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated, MyNotificationPermission,)
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)
    filterset_class = NotificationFilterSet
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter,)
    ordering_fields = ['created_at', 'status', 'id', ]
    http_method_names = ['get', 'patch', 'delete']

    def get_queryset(self):
        queryset = Notification.objects.none()
        user = self.request.user
        company = user.company
        if company:
            queryset = Notification.objects.filter(
                user=user, organization=company).order_by('status', '-id')
        return queryset

    @list_route(methods=['get'])
    def read_all_notifications(self, request, pk=None):
        """
        ```
        * To make all notification read pass
            *read_all=true* as query params
        * To make limited notification marked as
            read pass id of notification in *pk_list*
            Ex: ?pk_list=1,2,3
        ```
        """
        user = request.user
        company = user.company
        pk_list = request.GET.getlist('pk_list', [])
        read_all = True if self.request.query_params.get(
            "read_all") == 'true' else False
        if read_all:
            Notification.objects.filter(
                user=user, organization=company, status=1).update(status=2)
            return Response(
                {"detail": "Notifications Successfully Read by the User."},
                status=200)
        elif pk_list:
            pk_list = list(map(int, pk_list[0].split(',')))
            records_updated = Notification.objects.filter(
                pk__in=pk_list, user=user,
                organization=company, status=1).update(status=2)
            if records_updated:
                return Response(
                    {"detail": "Notifications Successfully "
                               "Read by the User."},
                    status=200)
        else:
            return Response({"detail": "No Notification Available."},
                            status=400)

    def destroy(self, request, *args, **kwargs):
        instance = get_object_or_404(self.get_queryset(),
                                     pk=int(kwargs.get('pk')))
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AskTaskUpdateAPIView(GenericAPIView):
    """
        Description : This API will email the user asking about the task
        Method  : POST
        url     : notifications/api/taskupdate/
        POST_PARAM : task_id
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = AskTaskUpdateSerializer
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)

    def get_queryset(self):
        user = self.request.user
        company = user.company
        queryset = Task.objects.none()
        if user_permission_check(user, 'task'):
            q_obj = Q()
            q_obj.add(Q(is_private=True, organization=company) &
                      Q(Q(assigned_to=user) |
                        Q(created_by=user) |
                        Q(assigned_to_group__group_members=user)), Q.OR)
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = Task.objects.filter(q_obj).distinct('id').exclude(
                status__in=[3, 4])
        else:
            queryset = Task.objects.exclude(status__in=[3, 4]).filter(
                Q(organization=company),
                Q(assigned_to=user) |
                Q(created_by=user) |
                Q(assigned_to_group__group_members=user)
            ).distinct('id')
        return queryset

    def post(self, request):
        user = request.user
        company = user.company
        group = user.group
        queryset = self.filter_queryset(self.get_queryset())
        # check permission for send ping
        if not GroupAndPermission.objects.filter(
                group=group,
                permission__name="Send Ping",
                company=company,
                has_permission=True
        ).exists():
            return Response({
                "detail": "You do not have permission "
                          "to perform this action."
            }, status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.validated_data.get('task')
        if task and queryset.filter(id=task.id).exists():
            task_ping_notification(task, user)
            AuditHistoryCreate(
                "task", task.id, user, "Ping Sent at")
            return Response({
                "detail": "Email Notification Sent Successfully!"
            }, status.HTTP_200_OK)
        else:
            return Response({
                "detail": "Ping can not be sent from "
                          "archive/completed task!"
            }, status.HTTP_400_BAD_REQUEST)


class CompanyUserNotificationSettingViewSet(viewsets.ModelViewSet):
    """
     partial_update:
     # just company owner and company admin
       has permission to update any
     user's notification setting
     API to update user-notification settings
    ```
     * change notification setting
     To update user-notification setting:
        pass User id as id
        'in_app_notification':[notification IDs]
       'email_notification':[notification ids]
     ```
     """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)
    serializer_class = UserNotificationSettingSerializer
    queryset = User.objects.all()
    http_method_names = ['patch']

    def update(self, request, *args, **kwargs):
        user = request.user
        company = user.company
        instance = User.objects.filter(pk=int(kwargs.get('pk')),
                                       company=company, is_delete=False
                                       ).first()
        if not instance:
            return Response(
                {'detail': "User does not exist"},
                status=status.HTTP_400_BAD_REQUEST)
        if instance.is_owner and not user.is_owner:
            return Response(
                {'detail': "You don't have permission to "
                           "perform this action"},
                status=status.HTTP_400_BAD_REQUEST)
        UserNotificationSetting.objects.filter(user=instance).delete()
        if request.data.get('in_app_notification'):
            for in_app_notification in request.data.get('in_app_notification'):
                UserNotificationSetting.objects.create(
                    in_app_notification=True,
                    email_notification=False,
                    user=instance,
                    notification_type=NotificationType.objects.get(
                        pk=in_app_notification))
        if request.data.get('email_notification'):
            for email_notification in request.data.get('email_notification'):
                UserNotificationSetting.objects.create(
                    in_app_notification=False,
                    email_notification=True,
                    user=instance,
                    notification_type=NotificationType.objects.get(
                        pk=email_notification))
        return Response({"detail": "Notification Updated Successfully!"})


class UserNotificationSettingViewSet(viewsets.ModelViewSet):
    """
     partial_update:
     API to update user-notification settings
    ```
     * change notification setting
     To update user-notification setting:
        pass User id as id
        'in_app_notification':[notification IDs]
       'email_notification':[notification ids]
     ```
     """
    permission_classes = (IsAuthenticated,)
    serializer_class = UserNotificationSettingSerializer
    queryset = User.objects.all()
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        user = request.user
        UserNotificationSetting.objects.filter(
            user=user).delete()
        if request.data.get('in_app_notification'):
            for in_app_notification in request.data.get('in_app_notification'):
                UserNotificationSetting.objects.create(
                    in_app_notification=True,
                    email_notification=False,
                    user=user,
                    notification_type=NotificationType.objects.get(
                        pk=in_app_notification))
        if request.data.get('email_notification'):
            for email_notification in request.data.get('email_notification'):
                UserNotificationSetting.objects.create(
                    in_app_notification=False,
                    email_notification=True,
                    user=user,
                    notification_type=NotificationType.objects.get(
                        pk=email_notification))
        return Response({"detail": "Notification "
                                   "Updated Successfully!"})


class CompanyUserNotificationViewSet(viewsets.ModelViewSet):
    """
     list:
     API to get list of notification assigned to
        user including notification type

     * API to get list of notification
     ```
     > pass user_id of user
      e.g.: ?user_id=1
     > filter by notification category
        choices=task,workflow,project,account
        e.g. &model_type=account
     ```
     """
    permission_classes = (PermissionManagerPermission,
                          CompanyUserNotificationPermission,)
    serializer_class = CompanyUserNotificationSerializer
    http_method_names = ['get']

    def get_queryset(self):
        model_type = self.request.query_params.get('model_type', '')
        queryset = NotificationType.objects.all()
        model_choices = list(
            map(lambda x: x[0].lower(), NOTIFICATION_CATEGORY_CHOICES))
        if model_type and model_type.lower() in model_choices:
            return queryset.filter(notification_category=model_type.lower())
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user = request.user
        company = user.company
        user_id = self.request.query_params.get('user_id', '')
        if user_id and str(user_id).isdigit():
            instance = User.objects.filter(
                id=int(user_id), company=company, is_delete=False).first()
            if instance:
                serializer_class = CompanyUserNotificationSerializer(
                    queryset,
                    context={'request': request, "instance": instance},
                    many=True)
                return Response(serializer_class.data,
                                status=status.HTTP_200_OK)
            return Response({"detail": "User does not exist"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "please enter user id"},
                        status=status.HTTP_400_BAD_REQUEST)


class UserNotificationViewSet(viewsets.ModelViewSet):
    """
     list:
     * API to get list of notification assigned
        to user including notification type
     ```
     > filter by notification category
        choices=task,workflow,project,account
        e.g. &model_type=account
     ```
     """
    permission_classes = (IsAuthenticated,
                          CompanyUserNotificationPermission,)
    serializer_class = CompanyUserNotificationSerializer
    http_method_names = ['get']

    def get_queryset(self):
        model_type = self.request.query_params.get('model_type', '')
        queryset = NotificationType.objects.all()
        model_choices = list(
            map(lambda x: x[0].lower(), NOTIFICATION_CATEGORY_CHOICES))
        if model_type and model_type.lower() in model_choices:
            return queryset.filter(
                notification_category=model_type.lower())
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user = request.user
        company = user.company
        if company and not user.is_delete:
            serializer_class = CompanyUserNotificationSerializer(
                queryset,
                context={'request': request, "instance": user},
                many=True)
            return Response(serializer_class.data,
                            status=status.HTTP_200_OK)
        return Response({"detail": "User does not exist"},
                        status=status.HTTP_400_BAD_REQUEST)
