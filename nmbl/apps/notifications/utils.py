from authentication.adapters import get_invitations_adapter
from authentication.tasks import send_celery_email
from django.conf import settings
from django.core.mail import EmailMessage

from .models import Notification, UserNotificationSetting, NotificationType


def send_user_notification(title, notification_type, user, notified_url,
                           email_template='', context=None,
                           from_email=None):
    print('send_user_notification', title,
          notification_type, user, notified_url)
    try:
        notification_type = \
            NotificationType.objects.get(slug=notification_type)
    except Exception as e:
        print('Error: Notification send_user_notification', e)
        notification_type = None

    try:
        notification_setting = UserNotificationSetting.objects.filter(
            user=user, notification_type=notification_type)
        if notification_setting:
            if notification_setting.filter(in_app_notification=True).exists():
                data_dict = {"title": title, "message_body": title,
                             "notification_type": notification_type,
                             "user": user, "notification_url": notified_url,
                             "status": 1}
                notification = Notification.objects.create(**data_dict)
                notification.notify_ws_clients()

            if notification_setting.filter(email_notification=True).exists():
                print('user.email: ', user.email)
                send_celery_email.delay(email_template,
                                        user.email, context,
                                        title, from_email)
    except Exception as e:
        print('Error: Email send_user_notification', str(e))
        return False


def send_email_notification(email, message_body, notified_url, subject):
    from django.db import connection
    site = settings.NOTIFICATION_BASE_URL.format(connection.schema_name)
    new_url = site + "/main/" + notified_url
    context = {"notified_url": new_url}
    email_template = 'notification/email_notification'
    get_invitations_adapter().send_mail(email_template,
                                        email, context, subject)


def send_by_template(template_obj, email, email_from):
    try:
        subject = template_obj.subject
        message = template_obj.message
        msg = EmailMessage(subject, message, to=(email,),
                           from_email=email_from)
        msg.content_subtype = 'text'
        msg.send()
        return True
    except Exception as e:
        print("Some error :", str(e))
        return False
