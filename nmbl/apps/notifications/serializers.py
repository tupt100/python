from notifications.models import Notification, \
    UserNotificationSetting, NotificationType
from projects.models import Task
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'status', 'title',
                  'notification_url', 'created_at', ]
        read_only_fields = ['id', 'created_at', 'title',
                            'notification_url', ]


class AskTaskUpdateSerializer(serializers.Serializer):
    task_id = serializers.CharField()

    def validate(self, attrs):
        task_id = attrs.get('task_id')
        request = self.context.get('request')
        try:
            task = Task.objects.get(pk=task_id)
            attrs['task'] = task
        except Exception as e:
            print("exception:", e)
            raise ValidationError(
                {"detail": "You are not part of any organisation, "
                           "So you can't upload Documents"}
            )
        if task.organization != request.user.company:
            raise ValidationError(
                {"detail": "You are not authorized "
                           "to perform this action"}
            )
        return attrs


class NotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ["id", "name", "slug"]


class UserNotificationSettingSerializer(serializers.ModelSerializer):
    notification_type = NotificationTypeSerializer()

    class Meta:
        model = UserNotificationSetting
        fields = ['notification_type', ]


class CompanyUserNotificationSerializer(serializers.ModelSerializer):
    in_app_notification = serializers.SerializerMethodField()
    email_notification = serializers.SerializerMethodField()

    class Meta:
        model = NotificationType
        fields = ["id", "name", "in_app_notification",
                  "email_notification", ]

    def get_in_app_notification(self, obj):
        user_obj = self.context['instance']
        return UserNotificationSetting.objects.filter(
            user=user_obj, notification_type=obj,
            in_app_notification=True).exists()

    def get_email_notification(self, obj):
        user_obj = self.context['instance']
        return UserNotificationSetting.objects.filter(
            user=user_obj, notification_type=obj,
            email_notification=True).exists()
