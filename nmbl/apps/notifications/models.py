from asgiref.sync import async_to_sync
from authentication.models import BaseModel, Group, Organization
from django.conf import settings
from django.db import models, connection
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

STATUS_CHOICES = (
    (1, _("Unread")),
    (2, _("Read"))
)

NOTIFICATION_CATEGORY_CHOICES = (
    ('task', _("Task")),
    ('workflow', _("Workflow")),
    ('project', _("Project")),
    ('account', _("Account")),
)


class NotificationType(BaseModel):
    name = models.CharField(max_length=254, db_index=True,
                            verbose_name=_('Notification Name'))
    slug = models.SlugField(unique=True, null=True, blank=True)
    notification_category = models.CharField(
        max_length=100, verbose_name=_('Notification Category'),
        choices=NOTIFICATION_CATEGORY_CHOICES, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name.replace(" ", "_").lower())
        super(NotificationType, self).save(*args, **kwargs)

    class Meta:
        unique_together = ["name", "slug"]

    def __str__(self):
        return str(self.name)


class Notification(BaseModel):
    status = models.IntegerField(verbose_name=_('Status'),
                                 choices=STATUS_CHOICES, default=1)
    is_notify = models.BooleanField(verbose_name=_('Notified'), default=False)
    title = models.CharField(max_length=254, db_index=True,
                             verbose_name=_('Title'))
    notification_type = models.ForeignKey(NotificationType, null=True,
                                          blank=True, on_delete=models.CASCADE,
                                          related_name='notification_type',
                                          verbose_name=_('Notification Name'))
    message_body = models.TextField(verbose_name=_('Message Content'),
                                    null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             null=True, blank=True,
                             on_delete=models.CASCADE,
                             related_name='notification_user')
    organization = models.ForeignKey(Organization, null=True,
                                     verbose_name=_('Company'), blank=True,
                                     on_delete=models.CASCADE,
                                     related_name='notification_organization')
    notification_url = models.CharField(_("Notification Related Url"),
                                        max_length=254, blank=True)

    def notify_ws_clients(self):
        """
        Inform client there is a new message.
        """
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()

        try:
            async_to_sync(channel_layer.group_send)(
                'user_channel_{}'.format(self.user.id), {
                    "type": "user.notification",
                    "username": self.user.username,
                    "title": self.title,
                    "message": self.message_body,
                })
        except Exception as e:
            raise e
        print("message sent")

    def __str__(self):
        return str(self.status or self.notification_type)


class OutgoingEmailTemplates(BaseModel):
    name = models.CharField(max_length=254, db_index=True,
                            verbose_name=_('Email Template Name'))
    subject = models.CharField(max_length=254)
    message = models.TextField(
        help_text="You can move or duplicate {} bracket words, "
                  "but you CANNOT edit or change the words inside.")


class UserNotificationSetting(BaseModel):
    in_app_notification = models.BooleanField(
        verbose_name=_('In App Notification'), default=False)
    email_notification = models.BooleanField(
        verbose_name=_('Email Notification'), default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='notification_setting_user')
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='notification_type_setting')

    def __str__(self):
        return str(self.notification_type.name or self.user.email)

    class Meta:
        unique_together = ["in_app_notification", "email_notification",
                           "user", "notification_type"]

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                'TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))


class DefaultUserNotificationSetting(BaseModel):
    in_app_notification = models.BooleanField(
        verbose_name=_('In App Notification'), default=False)
    email_notification = models.BooleanField(
        verbose_name=_('Email Notification'), default=False)
    notification_type = models.ForeignKey(
        NotificationType, on_delete=models.CASCADE,
        related_name='default_notification_type_setting')
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
