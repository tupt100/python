from celery import shared_task
from django.utils import six

try:
    import importlib
except ImportError:
    from django.utils import importlib
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.conf import settings


def import_attribute(path):
    assert isinstance(path, six.string_types)
    pkg, attr = path.rsplit('.', 1)
    ret = getattr(importlib.import_module(pkg), attr)
    return ret


def check_group_org_name_exists(group_name, org_name):
    try:
        from authentication.models import Group, Organization
        get_grp_ob = Group.objects.filter(name=group_name).first()
        get_org_ob = Organization.objects.filter(name=org_name)
        if get_grp_ob and get_org_ob.exists():
            return True
        else:
            return False
    except Exception as e:
        print(str(e))
        return False


def has_user_permission(request, permission):
    from authentication.models import GroupAndPermission
    try:
        user_company = request.user.company
        user_group = request.user.group

        obj = GroupAndPermission.objects.filter(group=user_group,
                                                company=user_company)
        has_permission = False
        for per in obj:
            if per.permission.slug == permission or \
                    (per.permission.slug.split("_")[1]).lower() == "all" \
                    and per.permission.slug.split("_")[0] == \
                    permission.split("_")[0]:
                has_permission = True
                break
            else:
                has_permission = False
        return has_permission
    except Exception as e:
        print(str(e))
        return False


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def notify_company_owner(user, old_group):
    from authentication.models import User
    from notifications.models import Notification
    company_owner = User.objects.get(company=user.company, is_owner=True)
    sub = '{} {} Role & Permission settings were updated ' \
          'from {} to {}'.format(user.first_name,
                                 user.last_name,
                                 old_group,
                                 user.group.name)
    subject = sub
    data_dict = {"title": subject, "message_body": subject,
                 "user": company_owner}
    notification = Notification.objects.create(**data_dict)
    notification.notify_ws_clients()


@shared_task
def invitation_send(user, invite):
    from django.db import connection
    owner_name = user.first_name
    user_email = invite.email
    group = invite.invited_by_group
    site = "PROXY by NMBL Technologies."
    base_url = settings.SITE_URL.format(
        connection.schema_name).replace(':8080', '')
    company = user.company
    invite_url = base_url + "/auth/signup/" + str(invite.key)
    ctx = {
        "email": user_email,
        "name": owner_name,
        "site_name": site,
        "group": group.name,
        "company": company,
        'invite_url': invite_url,
        'sender_name': owner_name,
    }
    subject = "You are invited to Join PROXY by NMBL Technologies"
    message = get_template(
        'invitations/email/email_invite_message.html').render(ctx)
    msg = EmailMessage(subject, message, to=(user_email,),
                       from_email='{} {} {} <{}>'.format(
                           user.first_name,
                           user.last_name,
                           "(PROXY)", settings.DEFAULT_FROM_EMAIL))

    msg.content_subtype = 'html'
    msg.send()


@shared_task
def user_group_change_notification(instance):
    from django.db import connection
    from notifications.utils import send_user_notification
    subject = "Your company's administrator has made " \
              "some changes to your role and permissions."
    notification_type = "role_update"
    notified_url = "main/settings/"
    email_template = 'notification/email_notification_role_update'
    site_url = settings.SITE_URL.format(
        connection.schema_name) + "/main/settings/"
    context = {
        'name': instance.first_name,
        'subject': subject,
        'company_name': instance.company.name,
        'site_url': site_url,
    }
    print("context: ", context)
    from_email = '{}<{}>'.format(
        "PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    send_user_notification(subject, notification_type, instance,
                           notified_url, email_template,
                           context, from_email)
