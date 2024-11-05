from django.contrib import admin

from .models import (Notification, NotificationType,
                     UserNotificationSetting,
                     OutgoingEmailTemplates,
                     DefaultUserNotificationSetting)


class NotificationAdmin(admin.ModelAdmin):
    list_display = ["status", "title", "notification_type",
                    "message_body", "user"]


class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "created_at",
                    "notification_category", ]
    list_filter = ("notification_category",)


class OutgoingEmailTemplatesAdmin(admin.ModelAdmin):
    list_display = ["name", "subject"]


class UserNotificationSettingAdmin(admin.ModelAdmin):
    list_display = ["user", "in_app_notification",
                    "email_notification",
                    "notification_type"]
    list_filter = ("user",)


class DefaultUserNotificationSettingAdmin(admin.ModelAdmin):
    list_display = ["group", "in_app_notification",
                    "email_notification",
                    "notification_type"]
    list_filter = ("group",)


admin.site.register(Notification, NotificationAdmin)
admin.site.register(NotificationType, NotificationTypeAdmin)
admin.site.register(OutgoingEmailTemplates,
                    OutgoingEmailTemplatesAdmin)
admin.site.register(UserNotificationSetting,
                    UserNotificationSettingAdmin)
admin.site.register(DefaultUserNotificationSetting,
                    DefaultUserNotificationSettingAdmin)
