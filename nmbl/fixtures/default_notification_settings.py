from authentication.models import User
from notifications.models import (UserNotificationSetting,
                                  DefaultUserNotificationSetting)

UserNotificationSetting.truncate()
for user in User.objects.all():
    for default_permission in \
            DefaultUserNotificationSetting.objects.filter(
                group=user.group):
        UserNotificationSetting.objects.create(
            user=user,
            in_app_notification=default_permission.in_app_notification,
            email_notification=default_permission.email_notification,
            notification_type=default_permission.notification_type,
        )
