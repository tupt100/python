import datetime
import logging
from urllib.parse import urlparse

from authentication.models import GroupAndPermission, Organization, User
from base.services.postmark import PostmarkInbound
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.template.loader import get_template
from django.utils.crypto import get_random_string
from notifications.utils import send_user_notification

from .models import (
    Attachment,
    AuditHistory,
    CompletionLog,
    GroupWorkLoadLog,
    Privilage_Change_Log,
    Project,
    ServiceDeskExternalCCUser,
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskRequestMessage,
    ServiceDeskUserInformation,
    Tag,
    TagChangeLog,
    Task,
    TeamMemberWorkLoadLog,
    Workflow,
    WorkProductivityLog,
)

try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text

import uuid
from datetime import timedelta

from django.utils import timezone
from notifications.models import Notification, NotificationType, UserNotificationSetting


def email_with_site_domain(mailbox_name):
    domain_name = urlparse(settings.SITE_URL).netloc
    return mailbox_name + "@" + domain_name


def complete_project(project, user):
    """
    This is to complete project related task and workflow
    :return:
    """
    project.workflow_assigned_project.update(status=2)
    workflow_ids = list(Workflow.objects.filter(project=project).values_list('id', flat=True))
    if workflow_ids:
        for workflow_id in workflow_ids:
            AuditHistoryCreate("workflow", workflow_id, user, "Marked Completed on")
    Task.objects.filter(workflow__project=project).update(status=3)
    task_ids = list(Task.objects.filter(workflow__project=project).values_list('id', flat=True))
    if task_ids:
        for task_id in task_ids:
            AuditHistoryCreate("task", task_id, user, "Marked Completed on")


def complete_workflow(workflow, user):
    """
    This is to complete workflow related task
    :return:
    """
    workflow.task_workflow.update(status=3)
    task_ids = list(Task.objects.filter(workflow=workflow).values_list('id', flat=True))
    if task_ids:
        for task_id in task_ids:
            AuditHistoryCreate("task", task_id, user, "Marked Completed on")
    else:
        pass


def archive_project(project):
    """
    This is to archive project related task and workflow
    :return:
    """
    project.workflow_assigned_project.update(status=3)
    Task.objects.filter(workflow__project=project).update(status=4)


def archive_workflow(workflow):
    """
    This is to archive workflow related task
    :return:
    """
    workflow.task_workflow.update(status=4)


def task_assigned_notification(task):
    if task.created_by == task.assigned_to:
        return
    from django.db import connection

    # Task is Assigned Email and app notification
    subject = "You Have a New Task"
    notification_type = "task_assigned_to_user"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_create_new_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {
        'user': task.assigned_to,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    from_email = '{} {}<{}>'.format(
        task.last_modified_by.first_name, task.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(
        subject, notification_type, task.assigned_to, notified_url, email_template, context, from_email
    )


def task_attachment_uploaded_notification(task, user, servicedesk_user=None):
    from django.db import connection

    subject = "A new document has been added to the following task"
    notification_type = "document_uploaded_to_task"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {
        'user': user,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    if servicedesk_user:
        from_email = '{}<{}>'.format(servicedesk_user.user_name, settings.DEFAULT_FROM_EMAIL)
    else:
        from_email = '{} {}<{}>'.format(
            task.last_modified_by.first_name, task.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
        )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def task_completed_notification(task, user):
    from django.db import connection

    subject = "The following task has now been marked as completed"
    notification_type = "task_is_completed"
    notified_url = "projects/task-archive"
    email_template = 'notification/email_notification_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/task-archive"
    context = {
        'user': user,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    from_email = '{} {}<{}>'.format(
        task.last_modified_by.first_name, task.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def task_due_date_notification(task):
    from django.db import connection

    subject = "The following task is now past its due date"
    notification_message = "{} is past its due date".format(task.name)
    notification_type = "task_due_date"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {
        'user': task.assigned_to,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    send_user_notification(
        notification_message, notification_type, task.assigned_to, notified_url, email_template, context, from_email
    )


def task_ping_notification(task, ping_user):
    from django.db import connection

    subject = "{} {} has requested an update about {}".format(ping_user.first_name, ping_user.last_name, task.name)
    notification_type = "task_ping"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_ping_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {
        'user': task.assigned_to,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    from_email = '{} {}<{}>'.format(ping_user.first_name, ping_user.last_name, settings.DEFAULT_FROM_EMAIL)
    send_user_notification(
        subject, notification_type, task.assigned_to, notified_url, email_template, context, from_email
    )


def project_assigned_notification(project, user):
    from django.db import connection

    subject = "You have been added to the following project"
    notification_type = "added_to_new_project"
    notified_url = "projects/" + str(project.pk)
    email_template = 'notification/email_notification_project'
    site_url = settings.SITE_URL.format(connection.schema_name)
    project_url = site_url + "/main/projects/" + str(project.pk)
    context = {
        'user': user,
        'subject': subject,
        'project_name': project.name,
        'project_url': project_url,
    }
    from_email = '{} {}<{}>'.format(
        project.last_modified_by.first_name, project.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def project_removed_notification(project, user):
    from django.db import connection

    subject = "You have been removed from the following project"
    notification_type = "removed_from_project"
    notified_url = "projects/"
    email_template = 'notification/email_notification_project'
    site_url = settings.SITE_URL.format(connection.schema_name)
    project_url = site_url + "/main/projects/"
    context = {
        'user': user,
        'subject': subject,
        'project_name': project.name,
        'project_url': project_url,
        'removed': True,
    }
    from_email = '{} {}<{}>'.format(
        project.last_modified_by.first_name, project.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def project_completed_notification(project, user):
    from django.db import connection

    subject = "The following project has now been marked as completed"
    notification_type = "project_is_completed"
    notified_url = "projects/archive"
    email_template = 'notification/email_notification_project'
    site_url = settings.SITE_URL.format(connection.schema_name)
    project_url = site_url + "/main/projects/archive"
    context = {
        'user': user,
        'subject': subject,
        'project_name': project.name,
        'project_url': project_url,
    }
    from_email = '{} {}<{}>'.format(
        project.last_modified_by.first_name, project.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def project_attachment_uploaded_notification(project, user, servicedesk_user=None):
    from django.db import connection

    subject = "A new document has been added to the following project"
    notification_type = "document_uploaded_to_project"
    notified_url = "projects/" + str(project.pk)
    email_template = 'notification/email_notification_project'
    site_url = settings.SITE_URL.format(connection.schema_name)
    project_url = site_url + "/main/projects/" + str(project.pk)
    context = {
        'user': user,
        'subject': subject,
        'project_name': project.name,
        'project_url': project_url,
    }
    if servicedesk_user:
        from_email = '{}<{}>'.format(servicedesk_user.user_name, settings.DEFAULT_FROM_EMAIL)
    else:
        from_email = '{} {}<{}>'.format(
            project.last_modified_by.first_name, project.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
        )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def project_due_date_notification(project, user):
    from django.db import connection

    subject = "The following project is now past its due date"
    notification_message = "{} is past its due date".format(project.name)
    notification_type = "project_due_date"
    notified_url = "projects/" + str(project.pk)
    email_template = 'notification/email_notification_project'
    site_url = settings.SITE_URL.format(connection.schema_name)
    project_url = site_url + "/main/projects/" + str(project.pk)
    context = {
        'user': user,
        'subject': subject,
        'project_name': project.name,
        'project_url': project_url,
    }
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    send_user_notification(
        notification_message, notification_type, user, notified_url, email_template, context, from_email
    )


def workflow_assigned_notification(workflow, user):
    from django.db import connection

    subject = "You have been added to the following workflow"
    notification_type = "added_to_new_workflow"
    notified_url = "projects/workflow/" + str(workflow.pk)
    email_template = 'notification/email_notification_workflow'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workflow_url = site_url + "/main/projects/workflow/" + str(workflow.pk)
    context = {
        'user': user,
        'subject': subject,
        'workflow_name': workflow.name,
        'workflow_url': workflow_url,
    }
    from_email = '{} {}<{}>'.format(
        workflow.last_modified_by.first_name, workflow.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def workflow_removed_notification(workflow, user):
    from django.db import connection

    subject = "You have been removed from the following workflow"
    notification_type = "removed_from_workflow"
    notified_url = "projects/list-workflow/"
    email_template = 'notification/email_notification_workflow'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workflow_url = site_url + "/main/projects/list-workflow/"
    context = {
        'user': user,
        'subject': subject,
        'workflow_name': workflow.name,
        'workflow_url': workflow_url,
        'removed': True,
    }
    from_email = '{} {}<{}>'.format(
        workflow.last_modified_by.first_name, workflow.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def workflow_completed_notification(workflow, user):
    from django.db import connection

    subject = "The following workflow has now been marked as completed"
    notification_type = "workflow_is_completed"
    notified_url = "projects/workflow-archive"
    email_template = 'notification/email_notification_workflow'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workflow_url = site_url + "/main/projects/workflow-archive/"
    context = {
        'user': user,
        'subject': subject,
        'workflow_name': workflow.name,
        'workflow_url': workflow_url,
    }
    from_email = '{} {}<{}>'.format(
        workflow.last_modified_by.first_name, workflow.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )

    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def workflow_due_date_notification(workflow, user):
    from django.db import connection

    subject = "The following workflow is now past its due date"
    notification_message = "{} is past its due date".format(workflow.name)
    notification_type = "workflow_due_date"
    notified_url = "projects/workflow/" + str(workflow.pk)
    email_template = 'notification/email_notification_workflow'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workflow_url = site_url + "/main/projects/workflow/" + str(workflow.pk)
    context = {
        'user': user,
        'subject': subject,
        'workflow_name': workflow.name,
        'workflow_url': workflow_url,
    }
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    send_user_notification(
        notification_message, notification_type, user, notified_url, email_template, context, from_email
    )


def workflow_attachment_uploaded_notification(workflow, user, servicedesk_user=None):
    from django.db import connection

    subject = "A new document has been added to the following workflow"
    notification_type = "document_uploaded_to_workflow"
    notified_url = "projects/workflow/" + str(workflow.pk)
    email_template = 'notification/email_notification_workflow'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workflow_url = site_url + "/main/projects/workflow/" + str(workflow.pk)
    context = {
        'user': user,
        'subject': subject,
        'workflow_name': workflow.name,
        'workflow_url': workflow_url,
    }
    if servicedesk_user:
        from_email = '{}<{}>'.format(servicedesk_user.user_name, settings.DEFAULT_FROM_EMAIL)
    else:
        from_email = '{} {}<{}>'.format(
            workflow.last_modified_by.first_name, workflow.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
        )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def document_associate_history(model_reference, model_id, model_name, change_message, by_user):
    message = {change_message: model_name}
    AuditHistory.objects.create(
        model_reference=model_reference,
        model_id=model_id,
        by_user=by_user,
        change_message=message,
        model_name=model_name,
    )


def AuditHistoryCreate(model_reference, model_id, by_user, change_message, model_name=None):
    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
    if change_message in [
        "Viewed By",
        "Due Date Updated by",
        "Importance Updated by",
        "Notes Updated by",
        "Notes were Updated by",
        "Document downloaded",
        "Renamed by",
        "Submitted by",
    ]:
        message = {change_message: by_user.first_name + " " + by_user.last_name + " " + "at" + " " + created_at}
        AuditHistory.objects.create(
            model_reference=model_reference, model_id=model_id, by_user=by_user, change_message=message
        )
    elif change_message == "Re-assigned to":
        currant_user = User.objects.get(id=by_user["by"])
        message = {
            change_message: by_user["to"].first_name
            + " "
            + by_user["to"].last_name
            + " "
            + "at"
            + " "
            + created_at
            + " "
            + "by"
            + " "
            + currant_user.first_name
            + " "
            + currant_user.last_name
        }
        AuditHistory.objects.create(
            model_reference=model_reference,
            model_id=model_id,
            by_user=currant_user,
            change_message=message,
            to_user=by_user["to"],
        )
    elif change_message == "Added to":
        message = {
            change_message: "Importance"
            + " "
            + "at"
            + " "
            + created_at
            + " "
            + "by"
            + " "
            + by_user.first_name
            + " "
            + by_user.last_name
        }
        AuditHistory.objects.create(
            model_reference=model_reference,
            model_id=model_id,
            by_user=by_user,
            change_message=message,
            model_name=model_name,
        )
    else:
        message = {change_message: created_at + " " + "by" + " " + by_user.first_name + " " + by_user.last_name}
        AuditHistory.objects.create(
            model_reference=model_reference, model_id=model_id, by_user=by_user, change_message=message
        )


def handle_webhook_task_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower()
    # print('from_email: ', from_email)
    user = User.objects.filter(email=from_email, is_delete=False).last()
    # print('user: ', user)
    if user:
        company = user.company
        group = user.group
        permission_category = 'task'
        slug = permission_category + "_" + permission_category + '-create'
        group_permission = GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category=permission_category,
            permission__slug=slug,
            has_permission=True,
        ).exists()
        if not group_permission:
            return
        post_data = {
            'name': postmark_obj.subject,
            'organization': company,
            'importance': 2,  # default importance is Med
            'created_by': user,
            'status': 1,  # default status is New
            'assigned_to': user,
            'last_modified_by': user,
            'due_date': datetime.datetime.utcnow(),
        }
        if len(postmark_obj.to) > 1:
            to_email = postmark_obj.to[1]['Email']
            assigned_to = User.objects.filter(email=to_email, company=company, is_delete=False).last()
            if assigned_to:
                post_data['assigned_to'] = assigned_to
            else:
                post_data['assigned_to'] = user
        task = Task.objects.create(**post_data)
        from .tasks import create_taskrank

        create_taskrank(task)
        AuditHistoryCreate("task", task.id, user, "Created at")
        if postmark_obj.text_body.strip():
            ServiceDeskRequestMessage.objects.create(
                message=postmark_obj.text_body.strip(), task=task, created_by_user=user, is_internal_message=True
            )
            task.description = postmark_obj.text_body.strip()
            task.save()
        if postmark_obj.has_attachments:
            AuditHistoryCreate("task", task.id, user, "Document Uploaded at")
            if task.created_by == task.assigned_to:
                task_attachment_uploaded_notification(task, task.created_by)
            else:
                task_attachment_uploaded_notification(task, task.created_by)
                task_attachment_uploaded_notification(task, task.assigned_to)
            for attachment in postmark_obj.attachments:
                try:
                    local_path = '/tmp/'
                    attachment.download(local_path)
                    if attachment.name().split('.')[-1].lower() in [
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
                    ]:
                        content_type = ContentType.objects.get(app_label='projects', model='task')
                        attachment_obj = Attachment(
                            content_type=content_type, object_id=task.id, created_by=user, organization=company
                        )
                        random_doc_name = get_random_string(20) + "." + attachment.name().split('.')[-1]
                        with open(local_path + attachment.name(), 'rb') as f:
                            attachment_obj.document_name = attachment.name()
                            attachment_obj.document.save(random_doc_name, File(f))
                        attachment_obj.save()
                        AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
                        document_associate_history("attachment", attachment_obj.id, task.name, "Associated Task", user)
                        import os

                        os.remove(local_path + attachment.name())
                    else:
                        pass
                except Exception as e:
                    print("Error: PostmarkTaskWebHook ", e)
            # try:
            #     task_attachment_uploaded_notification(task)
            # except Exception as e:
            #     print('Error: PostmarkTaskWebHook')
    return JsonResponse({'status': 'ok'})


def handle_webhook_project_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower()
    # print('from_email: ', from_email)
    user = User.objects.filter(email=from_email, is_delete=False).last()
    # print('user: ', user)
    if user:
        company = user.company
        group = user.group
        # print(company, group)
        # print(postmark_obj.to)
        # print(postmark_obj.cc)
        # print(postmark_obj.attachments)
        permission_category = 'project'
        slug = permission_category + "_" + permission_category + '-create'
        group_permission = GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category=permission_category,
            permission__slug=slug,
            has_permission=True,
        ).exists()
        if not group_permission:
            return
        post_data = {
            'name': postmark_obj.subject,
            'organization': company,
            'importance': 2,  # default importance is Med
            'created_by': user,
            'owner': user,
            'status': 1,  # default status is Active
            'last_modified_by': user,
            'assigned_by': user,
            'due_date': datetime.datetime.utcnow(),
        }
        # if len(postmark_obj.to) > 1:
        #     to_email = postmark_obj.to[1]['Email']
        #     owner = User.objects.filter(
        #         email=to_email, company=company).last()
        #     if owner:
        #         post_data['owner'] = owner
        assigned_to_users = []
        if len(postmark_obj.cc) > 1:
            for assignee in postmark_obj.cc:
                assignee_email = assignee['Email']
                assignee = User.objects.filter(email=assignee_email.lower(), company=company, is_delete=False).last()
                if assignee:
                    assigned_to_users.append(assignee)
                else:
                    assigned_to_users.append(user)
        else:
            assigned_to_users.append(user)
        # post_data['assigned_to_users'] = assigned_to_users
        project = Project.objects.create(**post_data)
        from .tasks import create_projectrank

        create_projectrank(project)
        AuditHistoryCreate("project", project.id, user, "Created at")
        if postmark_obj.text_body.strip():
            ServiceDeskRequestMessage.objects.create(
                message=postmark_obj.text_body.strip(), project=project, created_by_user=user, is_internal_message=True
            )
            project.description = postmark_obj.text_body.strip()
            project.save()
        assigned_to_users = list(set(assigned_to_users))
        if assigned_to_users:
            for assignee in assigned_to_users:
                project.assigned_to_users.add(assignee)
                project_assigned_notification(project, assignee)
        if postmark_obj.has_attachments:
            AuditHistoryCreate("project", project.id, user, "Document Uploaded at")
            project_attachment_uploaded_notification(project, project.owner)
            for project_user in assigned_to_users:
                if project_user != project.owner:
                    project_attachment_uploaded_notification(project, project_user)
            for attachment in postmark_obj.attachments:
                save_attachment_from_email(attachment=attachment, instance_target_to=project, user=user)
    # print('PostmarkTaskWebHook POST: ', pprint(postmark_obj.source))
    return JsonResponse({'status': 'ok'})


def handle_webhook_workflow_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower()
    # print('from_email: ', from_email)
    user = User.objects.filter(email=from_email, is_delete=False).last()
    # print('user: ', user)
    if user:
        company = user.company
        group = user.group
        # print(company, group)
        # print(postmark_obj.to)
        # print(postmark_obj.cc)
        # print(postmark_obj.attachments)
        permission_category = 'workflow'
        slug = permission_category + "_" + permission_category + '-create'
        group_permission = GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category=permission_category,
            permission__slug=slug,
            has_permission=True,
        ).exists()
        if not group_permission:
            return
        post_data = {
            'name': postmark_obj.subject,
            'organization': company,
            'importance': 2,  # default importance is Med
            'created_by': user,
            'owner': user,
            'status': 1,  # default status is Active
            'last_modified_by': user,
            'due_date': datetime.datetime.utcnow(),
        }
        # if len(postmark_obj.to) > 1:
        #     to_email = postmark_obj.to[1]['Email']
        #     owner = User.objects.filter(
        #         email=to_email, company=company).last()
        #     if owner:
        #         post_data['owner'] = owner
        assigned_to_users = []
        if len(postmark_obj.cc) > 1:
            for assignee in postmark_obj.cc:
                assignee_email = assignee['Email']
                assignee = User.objects.filter(email=assignee_email, company=company, is_delete=False).last()
                if assignee:
                    assigned_to_users.append(assignee)
                else:
                    assigned_to_users.append(user)
        else:
            assigned_to_users.append(user)
        # post_data['assigned_to_users'] = assigned_to_users
        workflow = Workflow.objects.create(**post_data)
        if postmark_obj.text_body.strip():
            ServiceDeskRequestMessage.objects.create(
                message=postmark_obj.text_body.strip(),
                workflow=workflow,
                created_by_user=user,
                is_internal_message=True,
            )
            workflow.description = postmark_obj.text_body.strip()
            workflow.save()
        AuditHistoryCreate("workflow", workflow.id, user, "Created at")
        from .tasks import create_workflowrank

        create_workflowrank(workflow)
        assigned_to_users = list(set(assigned_to_users))
        if assigned_to_users:
            for assignee in assigned_to_users:
                workflow.assigned_to_users.add(assignee)
                workflow_assigned_notification(workflow, assignee)
        if postmark_obj.has_attachments:
            AuditHistoryCreate("workflow", workflow.id, user, "Document Uploaded at")
            workflow_attachment_uploaded_notification(workflow, workflow.owner)
            for workflow_user in assigned_to_users:
                if workflow_user != workflow.owner:
                    workflow_attachment_uploaded_notification(workflow, workflow_user)
            for attachment in postmark_obj.attachments:
                save_attachment_from_email(attachment=attachment, instance_target_to=workflow, user=user)

    # print('PostmarkTaskWebHook POST: ', pprint(postmark_obj.source))
    return JsonResponse({'status': 'ok'})


def audit_importance_history(model_reference, model_id, by_user, change_message, last_importance):
    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
    message = {change_message: created_at + " " + "by" + " " + by_user.first_name + " " + by_user.last_name}
    AuditHistory.objects.create(
        model_reference=model_reference,
        model_id=model_id,
        by_user=by_user,
        change_message=message,
        last_importance=last_importance,
    )


def audit_due_date_history(model_reference, model_id, by_user, change_message, old_due_date, new_due_date):
    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
    message = {change_message: created_at + " " + "by" + " " + by_user.first_name + " " + by_user.last_name}
    AuditHistory.objects.create(
        model_reference=model_reference,
        model_id=model_id,
        by_user=by_user,
        change_message=message,
        old_due_date=old_due_date,
        new_due_date=new_due_date,
    )


def ReformatAuditHistory(instance, timezone, old_due_date, new_due_date, change_message):
    timezone = timezone.strftime('%I:%M %p on %m/%d/%Y')
    importance = ['"Low"', '"Medium"', '"High"']
    if change_message in [
        "Viewed By",
        "Due Date Updated by",
        "Importance Updated by",
        "Notes Updated by",
        "Notes were Updated by",
        "Document downloaded by",
        "Document renamed by",
        "Renamed by",
        "Re-activated by",
    ]:
        message = {
            change_message: instance.get('by_user')['first_name']
            + " "
            + instance.get('by_user')['last_name']
            + " "
            + "at"
            + " "
            + timezone
        }
    elif change_message == "Re-assigned to":
        to_user = User.objects.get(id=instance.get('to_user'))
        message = {
            change_message: to_user.first_name
            + " "
            + to_user.last_name
            + " "
            + "at"
            + " "
            + timezone
            + " "
            + "by"
            + " "
            + instance.get('by_user')['first_name']
            + " "
            + instance.get('by_user')['last_name']
        }
    elif change_message == "Changed to":
        message = {
            change_message: importance[instance.get('last_importance') - 1]
            + " "
            + "Importance"
            + " "
            + "at"
            + " "
            + timezone
            + " "
            + "by"
            + " "
            + instance.get('by_user')['first_name']
            + " "
            + instance.get('by_user')['last_name']
        }
    elif change_message == "Due Date changed":
        if not old_due_date and new_due_date:
            message = {
                change_message: "from"
                + " "
                + "None"
                + " "
                + "to"
                + " "
                + new_due_date.strftime('%D')
                + " "
                + "by"
                + " "
                + instance.get('by_user')['first_name']
                + " "
                + instance.get('by_user')['last_name']
                + " "
                + "at"
                + " "
                + timezone
            }
        elif not new_due_date and old_due_date:
            message = {
                change_message: "from"
                + " "
                + old_due_date.strftime('%D')
                + " "
                + "to"
                + " "
                + "None"
                + " "
                + "by"
                + " "
                + instance.get('by_user')['first_name']
                + " "
                + instance.get('by_user')['last_name']
                + " "
                + "at"
                + " "
                + timezone
            }
        else:
            message = {
                change_message: "from"
                + " "
                + old_due_date.strftime('%D')
                + " "
                + "to"
                + " "
                + new_due_date.strftime('%D')
                + " "
                + "by"
                + " "
                + instance.get('by_user')['first_name']
                + " "
                + instance.get('by_user')['last_name']
                + " "
                + "at"
                + " "
                + timezone
            }
    elif change_message == "Added to":
        message = {
            change_message: instance.get('model_name')
            + " "
            + "by"
            + " "
            + instance.get('by_user')['first_name']
            + " "
            + instance.get('by_user')['last_name']
            + " "
            + "at"
            + " "
            + timezone
        }
    elif change_message in ["Associated Project", "Associated Workflow", "Associated Task"]:
        message = {change_message + ":": instance.get('model_name')}
    elif change_message == "Submitted by":
        if instance.get('by_user'):
            message = {
                change_message: instance.get('by_user')['first_name']
                + " "
                + instance.get('by_user')['last_name']
                + " "
                + "at"
                + " "
                + timezone
            }
        elif instance.get('by_servicedesk_user'):
            message = {change_message: instance.get('by_servicedesk_user')['user_name'] + " " + "at" + " " + timezone}
        else:
            message = None
    else:
        if instance.get('by_user'):
            message = {
                change_message: timezone
                + " "
                + "by"
                + " "
                + instance.get('by_user')['first_name']
                + " "
                + instance.get('by_user')['last_name']
            }
        elif instance.get('by_servicedesk_user'):
            message = {change_message: timezone + " " + "by" + " " + instance.get('by_servicedesk_user')['user_name']}
        else:
            message = None
    return message


def GetOrCreateTags(tag, organization):
    tag = tag.upper()
    instance, created = Tag.objects.get_or_create(tag=tag, organization=organization)
    return instance.id


def attachment_copy_or_move(destination_id, destination_type, source_id, source_type, attachment_id, operation, user):
    """
    Helper function to copy/move attachments.
    """
    attachment = Attachment.objects.filter(id=attachment_id, is_delete=False).first()
    content_type = ContentType.objects.get(app_label='projects', model=destination_type)
    if operation == "move":
        if destination_type == "project":
            # change the content types and object i
            # ds of the attachment to new models
            instance = Project.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Project", user)
            return attachment
        elif destination_type == "workflow":
            # change the content types and object ids
            # of the attachment to new models
            instance = Workflow.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Workflow", user)
            return attachment
        elif destination_type == "task":
            # change the content types and object
            # ids of the attachment to new models
            instance = Task.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Task", user)
            return attachment
    elif operation == "copy":
        if destination_type == "project":
            instance = Project.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            # create a new document name
            copy_doc_name = get_random_string(20) + "." + attachment.document.name.split('.')[-1]
            # read the existing document from storage.
            read_file = default_storage.open(attachment.document.name, 'r')
            # create a new file
            write_file = default_storage.open("Documents/{}".format(copy_doc_name), 'w')
            new_doc_name = write_file.name
            write_file.write(read_file.read())
            read_file.close()
            write_file.close()
            attachment.document = new_doc_name
            # clone the attachment object with new file path.
            attachment.pk = None
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Project", user)
            return attachment
        elif destination_type == "workflow":
            instance = Workflow.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            # create a new document name
            copy_doc_name = get_random_string(20) + "." + attachment.document.name.split('.')[-1]
            read_file = default_storage.open(attachment.document.name, 'r')
            # create new file.
            write_file = default_storage.open("Documents/{}".format(copy_doc_name), 'w')
            new_doc_name = write_file.name
            write_file.write(read_file.read())
            read_file.close()
            write_file.close()
            attachment.document = new_doc_name
            # clone the attachment object with new file.
            attachment.pk = None
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Workflow", user)
            return attachment
        elif destination_type == "task":
            instance = Task.objects.filter(id=destination_id).first()
            attachment.content_type = content_type
            attachment.object_id = instance.id
            # create a new document name.
            copy_doc_name = get_random_string(20) + "." + attachment.document.name.split('.')[-1]
            read_file = default_storage.open(attachment.document.name, 'r')
            # create new file.
            write_file = default_storage.open("Documents/{}".format(copy_doc_name), 'w')
            new_doc_name = write_file.name
            write_file.write(read_file.read())
            read_file.close()
            write_file.close()
            attachment.document = new_doc_name
            # clone the attachment object with new file.
            attachment.pk = None
            attachment.save()
            document_associate_history("attachment", attachment.id, instance.name, "Associated Task", user)
            return attachment
    else:
        return None


def user_permission_check(user, model):
    view_all_slug = model + '_' + model + '-view-all'
    view_mine_slug = model + '_' + model + '-view'
    if GroupAndPermission.objects.filter(
        group=user.group, company=user.company, has_permission=True, permission__slug=view_all_slug
    ).exists():
        return True
    elif GroupAndPermission.objects.filter(
        group=user.group, company=user.company, has_permission=True, permission__slug=view_mine_slug
    ).exists():
        return False
    else:
        raise Http404


def user_has_object_permission(model, instance_id, user):
    """
    Function checks if the user is authorized
    to access the resource.
    """
    permission_count = 0
    if model == "task":
        if (
            Task.objects.filter(
                Q(organization=user.company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            )
            .filter(id=instance_id)
            .exists()
        ):
            permission_count += 1
    elif model == "workflow":
        if (
            Workflow.objects.filter(
                Q(organization=user.company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            )
            .filter(id=instance_id)
            .exists()
        ):
            permission_count += 1
    elif model == "project":
        if (
            Project.objects.filter(
                Q(organization=user.company),
                Q(owner=user)
                | Q(assigned_to_users=user)
                | Q(created_by=user)
                | Q(assigned_to_group__group_members=user),
            )
            .filter(id=instance_id)
            .exists()
        ):
            permission_count += 1
    return permission_count


def user_object_permission(model, instance_id, user):
    """
    Function checks if the user is authorized
    to access the resource.
    """
    permission_count = 0
    if model == "task":
        q_obj = Q()
        q_obj.add(
            Q(is_private=True, organization=user.company)
            & Q(Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user)),
            Q.OR,
        )
        q_obj.add(Q(is_private=False, organization=user.company), Q.OR)
        if Task.objects.filter(q_obj).filter(id=instance_id).exists():
            permission_count += 1
    elif model == "workflow":
        if Workflow.objects.filter(organization=user.company, id=instance_id).exists():
            permission_count += 1
    elif model == "project":
        if Project.objects.filter(organization=user.company, id=instance_id).exists():
            permission_count += 1
    return permission_count


def user_attachment_authorization_permission(source_type, source_id, destination_type, destination_id, user):
    source_view_all_slug = source_type + '_' + source_type + '-view-all'
    destination_view_all_slug = destination_type + '_' + destination_type + '-view-all'
    source_mine_slug = source_type + '_' + source_type + '-view'
    destination_mine_slug = destination_type + '_' + destination_type + '-view'
    # Return true if the user has view all permission
    # for both source and destination.
    if (
        GroupAndPermission.objects.filter(
            group=user.group, company=user.company, has_permission=True, permission__slug=source_view_all_slug
        ).exists()
        and GroupAndPermission.objects.filter(
            group=user.group, company=user.company, has_permission=True, permission__slug=destination_view_all_slug
        ).exists()
    ):
        soucre_permission_count = user_object_permission(source_type, source_id, user)
        destination_permission_count = user_object_permission(destination_type, destination_id, user)
        if soucre_permission_count + destination_permission_count == 2:
            return True
    # Else check if the user has view-mine permissions and
    # return if exists
    # forboth source and destination.
    elif (
        GroupAndPermission.objects.filter(
            group=user.group, company=user.company, has_permission=True, permission__slug=source_mine_slug
        ).exists()
        and GroupAndPermission.objects.filter(
            group=user.group, company=user.company, has_permission=True, permission__slug=destination_mine_slug
        ).exists()
    ):
        soucre_permission_count = user_has_object_permission(source_type, source_id, user)
        destination_permission_count = user_has_object_permission(destination_type, destination_id, user)
        if soucre_permission_count + destination_permission_count == 2:
            return True
    else:
        return False


def workgroup_assigned_notification(user, workgroup_member, workgroup):
    from django.db import connection

    subject = "You Have Been Added to the" + " " + workgroup.name + " " + "Group"
    notification_type = "workgroup_assigned_to_user"
    notified_url = "settings"
    email_template = 'notification/email_notification_workgroup_assigned'
    site_url = settings.SITE_URL.format(connection.schema_name)
    workgroup_url = site_url + "/main/settings"
    context = {
        'user': workgroup_member,
        'subject': subject,
        'workgroup_name': workgroup.name,
        'workgroup_url': workgroup_url,
    }
    from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)
    send_user_notification(
        subject, notification_type, workgroup_member, notified_url, email_template, context, from_email
    )


def task_assigned_to_group_notification(task, workgroup, user):
    from django.db import connection

    subject = "New Task for" + " " + workgroup.name + " " + "Group"
    notification_type = "task_assigned_to_user"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_task_assigned_to_group'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {'user': user, 'subject': subject, 'task_name': task.name, 'task_url': task_url, 'workgroup': workgroup}
    from_email = '{} {}<{}>'.format(
        task.last_modified_by.first_name, task.last_modified_by.last_name, settings.DEFAULT_FROM_EMAIL
    )
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def task_due_date_to_group_notification(task, user):
    from django.db import connection

    subject = "The following task is now past its due date"
    notification_type = "task_due_date"
    notified_url = "projects/tasks/" + str(task.pk)
    email_template = 'notification/email_notification_task'
    site_url = settings.SITE_URL.format(connection.schema_name)
    task_url = site_url + "/main/projects/tasks/" + str(task.pk)
    context = {
        'user': user,
        'subject': subject,
        'task_name': task.name,
        'task_url': task_url,
    }
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    send_user_notification(subject, notification_type, user, notified_url, email_template, context, from_email)


def ServiceDeskRequestAuditHistory(model_reference, model_id, user_by, change_message):
    created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
    message = {change_message: user_by.user_name + " " + "at" + " " + created_at}
    AuditHistory.objects.create(
        model_reference=model_reference, model_id=model_id, change_message=message, by_servicedesk_user=user_by
    )


@shared_task
def send_notification_to_user(request):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    company = request.user_information.organization
    if request.user_information.is_expire:
        request.user_information.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        request.user_information.expiration_date = timezone.now() + timedelta(7)
        request.user_information.is_expire = False
        request.user_information.save()
    service_desk_url = base_url + "/requests/pending-requests/" + str(request.user_information.access_token)
    ctx = {
        "company": company,
        'service_desk_url': service_desk_url,
    }
    subject = "Your Request was successfully " "submitted to {}.".format(company)
    message = get_template('notification/request_submit_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        subject,
        message,
        to=(request.user_information.user_email,),
        from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def resend_link_to_user(request):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    service_desk_url = base_url + "/requests/pending-requests/" + str(request.access_token)
    ctx = {
        'service_desk_url': service_desk_url,
    }
    subject = "Access link for your Pending Request(s)"
    prefix = "[{name}] ".format(name="PROXY")
    subject = prefix + force_text(subject)
    message = get_template('notification/resent_servicedesk_link_message.html').render(ctx)
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    msg = EmailMessage(subject, message, to=(request.user_email,), from_email=from_email)
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def new_request_notification_to_team_member(instance):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    in_app_url = "/main/services/" + str(instance.pk)
    notification_url = base_url + in_app_url
    email_subject = "New request submitted by client via the Service Desk!"
    prefix = "[{name}] ".format(name="PROXY")
    email_subject = prefix + force_text(email_subject)

    company = instance.user_information.organization
    subject = "New Service Desk Request"
    users = User.objects.filter(
        company=company,
        is_active=True,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='request_request-view',
    ).distinct('id')
    bulk__list = []
    [
        bulk__list.append(Notification(title=subject, message_body=subject, user=user, notification_url=in_app_url))
        for user in users
    ]
    notification = Notification.objects.bulk_create(bulk__list)
    [notification_obj.notify_ws_clients() for notification_obj in notification]
    ctx = {
        'notification_url': notification_url,
        'company_name': company.name,
    }
    from_email = '{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    to_emails = users.values_list('email', flat=True)[::1]
    message = get_template('notification/new_request_notification_to_team_member_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=to_emails,
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


def handle_webhook_request_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    if not postmark_obj.subject or not postmark_obj.text_body:
        subject = "[{name}] ".format(name="PROXY")
        message = (
            "Sorry! The request was not processed because you "
            "did not include a subject for the email or any "
            "instructions in the email body. Please try again."
        )
        msg = EmailMessage(
            subject, message, to=(from_email,), from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
        )
        msg.send()
        return JsonResponse({'status': 'ok'})
    company = Organization.objects.first()
    expiration_date = timezone.now() + timedelta(7)
    access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
    sender_name = postmark_obj.sender.get('Name').strip()
    user_obj = ServiceDeskUserInformation.objects.filter(organization=company, user_email=from_email).first()
    if not user_obj:
        user_data = {
            'user_name': sender_name,
            'user_email': from_email,
            'organization': company,
            'access_token': access_token,
            'expiration_date': expiration_date,
        }
        user_obj = ServiceDeskUserInformation.objects.create(**user_data)
    post_data = {
        'user_information': user_obj,
        'subject': postmark_obj.subject,
        'description': postmark_obj.text_body,
        'request_priority': 2,  # default importance is Med
        'requested_due_date': datetime.datetime.utcnow() + timedelta(14),
    }
    instance = ServiceDeskRequest.objects.create(**post_data)
    ServiceDeskRequestAuditHistory("servicedeskrequest", instance.id, instance.user_information, "Submitted by")
    # send notification to NRU for request
    # submitted successfully
    send_notification_to_user.delay(instance)
    new_request_notification_to_team_member.delay(instance)
    if postmark_obj.has_attachments:
        for attachment in postmark_obj.attachments:
            save_attachment_from_email(
                attachment=attachment,
                instance_target_to=instance,
                uploaded_by=user_obj,
                organization=company,
            )

    return JsonResponse({'status': 'ok'})


@shared_task
def request_complete_notification(instance, model, user):
    if model == "task":
        request_objs = ServiceDeskExternalRequest.objects.filter(task=instance)
    elif model == "project":
        request_objs = ServiceDeskExternalRequest.objects.filter(project=instance)
    elif model == "workflow":
        request_objs = ServiceDeskExternalRequest.objects.filter(workflow=instance)
    else:
        request_objs = None
    if request_objs:
        for request_obj in request_objs:
            from django.db import connection

            base_url = settings.SITE_URL.format(connection.schema_name)
            if request_obj.servicedeskuser.is_expire:
                request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
                request_obj.servicedeskuser.is_expire = False
                request_obj.servicedeskuser.save()
            service_desk_url = (
                base_url
                + "/requests/view-requests-current/"
                + str(request_obj.pk)
                + "/"
                + str(request_obj.servicedeskuser.access_token)
            )
            subject = "Request No {} is now complete!".format(request_obj.service_desk_request.id)
            prefix = "[{name}] ".format(name="PROXY")
            subject = prefix + force_text(subject)
            ctx = {
                'service_desk_url': service_desk_url,
                'user_name': request_obj.servicedeskuser.user_name,
                'company': instance.organization,
                'completed_by': user.first_name + " " + user.last_name,
                'request': instance.name,
                'request_no': request_obj.service_desk_request.id,
            }
            message = get_template('notification/request_complete_notification_message.html').render(ctx)
            msg = EmailMessage(
                subject,
                message,
                to=(request_obj.servicedeskuser.user_email,),
                from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
            )
            msg.content_subtype = 'html'
            msg.send()
        else:
            pass


@shared_task
def task_notify_user_for_new_message(request, instance, message_obj):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    notification_url = base_url + "/main/projects/tasks/" + str(instance.pk)
    in_app_url = "/main/projects/tasks/" + str(instance.pk)
    email_subject = "You Have a New Message regarding Request No. {}".format(request.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    email_subject = prefix + force_text(email_subject)
    related_users = []
    subject = "You have a new reply for request {}".format(request.service_desk_request.id)
    if instance.created_by not in related_users:
        related_users.append(instance.created_by)
    if instance.assigned_to and (instance.assigned_to not in related_users):
        related_users.append(instance.assigned_to)
    for group in instance.assigned_to_group.all():
        [related_users.append(group_member) for group_member in group.group_members.all()]
    bulk__list = []
    [
        bulk__list.append(Notification(title=subject, message_body=subject, user=user, notification_url=in_app_url))
        for user in related_users
    ]
    notification = Notification.objects.bulk_create(bulk__list)
    [notification_obj.notify_ws_clients() for notification_obj in notification]
    ctx = {
        'model': "Task",
        'notification_url': notification_url,
        'name': instance.name,
        'user_name': request.servicedeskuser.user_name,
        'message': message_obj.message,
    }
    from_email = '{}<{}>'.format(request.servicedeskuser.user_name, settings.DEFAULT_FROM_EMAIL)
    to_emails = [user.email for user in related_users]
    message = get_template('notification/task_new_reply_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=to_emails,
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def workflow_notify_user_for_new_message(request, instance, message_obj):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    notification_url = base_url + "/main/projects/workflow/" + str(instance.pk)
    in_app_url = "/main/projects/workflow/" + str(instance.pk)
    email_subject = "You Have a New Message regarding Request No. {}".format(request.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    email_subject = prefix + force_text(email_subject)
    related_users = []
    subject = "You have a new reply for request {}".format(request.service_desk_request.id)
    related_users.append(instance.owner)
    [
        related_users.append(workflow_user)
        for workflow_user in instance.assigned_to_users.all()
        if workflow_user not in related_users
    ]
    for group in instance.assigned_to_group.all():
        [related_users.append(group_member) for group_member in group.group_members.all()]
    bulk__list = []
    [
        bulk__list.append(Notification(title=subject, message_body=subject, user=user, notification_url=in_app_url))
        for user in related_users
    ]
    notification = Notification.objects.bulk_create(bulk__list)
    [notification_obj.notify_ws_clients() for notification_obj in notification]
    ctx = {
        'model': "Workflow",
        'notification_url': notification_url,
        'name': instance.name,
        'user_name': request.servicedeskuser.user_name,
        'message': message_obj.message,
    }
    from_email = '{}<{}>'.format(request.servicedeskuser.user_name, settings.DEFAULT_FROM_EMAIL)
    to_emails = [user.email for user in related_users]
    message = get_template('notification/task_new_reply_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=to_emails,
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def project_notify_user_for_new_message(request, instance, message_obj):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    notification_url = base_url + "/main/projects/" + str(instance.pk)
    in_app_url = "/main/projects/" + str(instance.pk)
    email_subject = "You Have a New Message regarding Request No. {}".format(request.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    email_subject = prefix + force_text(email_subject)
    related_users = []
    subject = "You have a new reply for request {}".format(request.service_desk_request.id)
    related_users.append(instance.owner)
    [
        related_users.append(project_user)
        for project_user in instance.assigned_to_users.all()
        if project_user not in related_users
    ]
    for group in instance.assigned_to_group.all():
        [related_users.append(group_member) for group_member in group.group_members.all()]
    bulk__list = []
    [
        bulk__list.append(Notification(title=subject, message_body=subject, user=user, notification_url=in_app_url))
        for user in related_users
    ]
    notification = Notification.objects.bulk_create(bulk__list)
    [notification_obj.notify_ws_clients() for notification_obj in notification]
    ctx = {
        'model': "Project",
        'notification_url': notification_url,
        'name': instance.name,
        'user_name': request.servicedeskuser.user_name,
        'message': message_obj.message,
    }
    from_email = '{}<{}>'.format(request.servicedeskuser.user_name, settings.DEFAULT_FROM_EMAIL)
    to_emails = [user.email for user in related_users]
    message = get_template('notification/task_new_reply_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=to_emails,
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def completed_request_reply(request, instance, message_obj, model):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    email_subject = "You Have a New Message regarding Request No. {}".format(request.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    email_subject = prefix + force_text(email_subject)
    if model == "task":
        model = "Task"
        notification_url = base_url + "/main/projects/tasks/" + str(instance.id)
    elif model == "project":
        model = "Project"
        notification_url = base_url + "/main/projects/" + str(instance.id)
    else:
        model = "Workflow"
        notification_url = base_url + "/main/projects/workflow/" + str(instance.id)
    ctx = {
        'model': model,
        'notification_url': notification_url,
        'name': instance.name,
        'user_name': request.servicedeskuser.user_name,
        'message': message_obj.message,
    }
    to_email = instance.last_modified_by.email
    from_email = '{}<{}>'.format(request.servicedeskuser.user_name, settings.DEFAULT_FROM_EMAIL)
    message = get_template('notification/task_new_reply_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=(to_email,),
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


def handle_message_task_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    try:
        to_email = postmark_obj.to[0]['Email']
        obj_ids = to_email.split('@')[0]
        user_id = int(obj_ids.split('.')[1])
        request_id = int(obj_ids.split('.')[2])
        task_id = int(obj_ids.split('.')[3])
        message_exist = False
        attachment_exist = False
        created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
        user_obj = ServiceDeskUserInformation.objects.filter(pk=user_id, user_email=from_email).first()
        if user_obj:
            request_obj = ServiceDeskRequest.objects.filter(pk=request_id, user_information=user_obj).first()
            if request_obj:
                task_obj = Task.objects.filter(pk=task_id).first()
                instance = ServiceDeskExternalRequest.objects.filter(
                    service_desk_request=request_obj, servicedeskuser=user_obj, task=task_obj
                ).first()
                if instance:
                    if postmark_obj.source['StrippedTextReply'].strip():
                        text = postmark_obj.source['StrippedTextReply'].strip()
                        message_obj = ServiceDeskRequestMessage.objects.create(
                            task=task_obj,
                            message=text,
                            reply_by_servicedeskuser=user_obj,
                            is_external_message=True,
                            servicedesk_request=request_obj,
                        )
                        message_exist = True
                        if task_obj.status in [3, 4]:
                            completed_request_reply.delay(instance, task_obj, message_obj, "task")
                            message_exist = False
                        else:
                            task_notify_user_for_new_message.delay(instance, task_obj, message_obj)
                    if postmark_obj.has_attachments and task_obj.status not in [3, 4]:
                        for attachment in postmark_obj.attachments:
                            attachment_exist = True
                            save_attachment_from_email(attachment, instance_target_to=task_obj, uploaded_by=user_obj)

                    if message_exist or attachment_exist:
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
                    if attachment_exist:
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
                        if instance.assigned_to_group:
                            for task_group in task_obj.assigned_to_group.all():
                                [
                                    task_attachment_uploaded_notification(task_obj, group_member, user_obj)
                                    for group_member in task_group.group_members.all()
                                ]
                    return JsonResponse({'status': 'ok'})
                else:
                    return JsonResponse({'status': 'ok'})
            else:
                return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'ok'})
    except Exception as e:
        print("exception:", e)
        return JsonResponse({'status': 'ok'})


def handle_message_project_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    try:
        to_email = postmark_obj.to[0]['Email']
        obj_ids = to_email.split('@')[0]
        user_id = int(obj_ids.split('.')[1])
        request_id = int(obj_ids.split('.')[2])
        project_id = int(obj_ids.split('.')[3])
        message_exist = False
        attachment_exist = False
        created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
        user_obj = ServiceDeskUserInformation.objects.filter(pk=user_id, user_email=from_email).first()
        if user_obj:
            request_obj = ServiceDeskRequest.objects.filter(pk=request_id, user_information=user_obj).first()
            if request_obj:
                project_obj = Project.objects.filter(pk=project_id).first()
                instance = ServiceDeskExternalRequest.objects.filter(
                    service_desk_request=request_obj, servicedeskuser=user_obj, project=project_obj
                ).first()
                if instance:
                    if postmark_obj.source['StrippedTextReply']:
                        message_obj = ServiceDeskRequestMessage.objects.create(
                            project=project_obj,
                            message=postmark_obj.source['StrippedTextReply'].strip(),
                            reply_by_servicedeskuser=user_obj,
                            is_external_message=True,
                        )
                        message_exist = True
                        if project_obj.status in [2, 3]:
                            completed_request_reply.delay(instance, project_obj, message_obj, "project")
                            message_exist = False
                        else:
                            project_notify_user_for_new_message.delay(instance, project_obj, message_obj)
                    if postmark_obj.has_attachments and project_obj.status in [1, 4, 5]:
                        for attachment in postmark_obj.attachments:
                            attachment_exist = True
                            save_attachment_from_email(
                                attachment, instance_target_to=project_obj, uploaded_by=user_obj
                            )
                    if message_exist or attachment_exist:
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
                    if attachment_exist:
                        project_doc_uploaded_message = {
                            "Document Uploaded at": created_at + " " + "by" + " " + user_obj.user_name
                        }
                        AuditHistory.objects.create(
                            model_reference="project",
                            model_id=project_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=project_doc_uploaded_message,
                        )
                        project_attachment_uploaded_notification(project_obj, project_obj.owner, user_obj)
                        if project_obj.assigned_to_users:
                            for project_user in project_obj.assigned_to_users.all():
                                if project_user != project_obj.owner:
                                    project_attachment_uploaded_notification(project_obj, project_user, user_obj)
                        if project_obj.assigned_to_group:
                            for projects_group in project_obj.assigned_to_group.all():
                                [
                                    project_attachment_uploaded_notification(project_obj, group_member, user_obj)
                                    for group_member in projects_group.group_members.all()
                                ]
                    return JsonResponse({'status': 'ok'})
                else:
                    return JsonResponse({'status': 'ok'})
            else:
                return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'ok'})
    except Exception as e:
        print("Error: PostmarkTaskWebHook ", e)
        return JsonResponse({'status': 'ok'})


def handle_message_workflow_inbound(data):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    try:
        to_email = postmark_obj.to[0]['Email']
        obj_ids = to_email.split('@')[0]
        user_id = int(obj_ids.split('.')[1])
        request_id = int(obj_ids.split('.')[2])
        workflow_id = int(obj_ids.split('.')[3])
        message_exist = False
        attachment_exist = False
        created_at = datetime.datetime.utcnow().strftime('%I:%M %P on %D')
        user_obj = ServiceDeskUserInformation.objects.filter(pk=user_id, user_email=from_email).first()
        if user_obj:
            request_obj = ServiceDeskRequest.objects.filter(pk=request_id, user_information=user_obj).first()
            if request_obj:
                workflow_obj = Workflow.objects.filter(pk=workflow_id).first()
                instance = ServiceDeskExternalRequest.objects.filter(
                    service_desk_request=request_obj, servicedeskuser=user_obj, workflow=workflow_obj
                ).first()
                if instance:
                    if postmark_obj.source['StrippedTextReply']:
                        text = postmark_obj.source['StrippedTextReply'].strip()
                        message_obj = ServiceDeskRequestMessage.objects.create(
                            workflow=workflow_obj,
                            message=text,
                            reply_by_servicedeskuser=user_obj,
                            is_external_message=True,
                        )
                        message_exist = True
                        if workflow_obj.status in [2, 3]:
                            message_exist = False
                            completed_request_reply.delay(instance, workflow_obj, message_obj, "workflow")
                        else:
                            workflow_notify_user_for_new_message.delay(instance, workflow_obj, message_obj)
                    if postmark_obj.has_attachments and workflow_obj.status in [1, 4, 5]:
                        for attachment in postmark_obj.attachments:
                            attachment_exist = True
                            save_attachment_from_email(
                                attachment=attachment,
                                instance_target_to=workflow_obj,
                                uploaded_by=user_obj,
                            )

                    if message_exist or attachment_exist:
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
                    if attachment_exist:
                        workflow_doc_uploaded_message = {
                            "Document Uploaded at": created_at + " " + "by" + " " + user_obj.user_name
                        }
                        AuditHistory.objects.create(
                            model_reference="workflow",
                            model_id=workflow_obj.id,
                            by_servicedesk_user=user_obj,
                            change_message=workflow_doc_uploaded_message,
                        )
                        workflow_attachment_uploaded_notification(workflow_obj, workflow_obj.owner, user_obj)
                        if workflow_obj.assigned_to_users:
                            for workflow_user in workflow_obj.assigned_to_users.all():
                                if workflow_user != workflow_obj.owner:
                                    workflow_attachment_uploaded_notification(workflow_obj, workflow_user, user_obj)
                        if workflow_obj.assigned_to_group:
                            for workflow_group in workflow_obj.assigned_to_group.all():
                                [
                                    workflow_attachment_uploaded_notification(workflow_obj, group_member, user_obj)
                                    for group_member in workflow_group.group_members.all()
                                ]
                    return JsonResponse({'status': 'ok'})
                else:
                    return JsonResponse({'status': 'ok'})
            else:
                return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'ok'})
    except Exception as e:
        print("exception:", e)
        return JsonResponse({'status': 'ok'})


@shared_task
def project_new_message_notification(message, project, user):
    request_obj = ServiceDeskExternalRequest.objects.filter(project=project).first()
    if request_obj:
        from django.db import connection

        base_url = settings.SITE_URL.format(connection.schema_name)
        schema_name = connection.schema_name
        importance = ["Low", "Medium", "High"]
        if request_obj.servicedeskuser.is_expire:
            request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
            request_obj.servicedeskuser.is_expire = False
            request_obj.servicedeskuser.save()
        service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
        subject = "You Have a New Message regarding Request No. {}".format(request_obj.service_desk_request.id)
        prefix = "[{name}] ".format(name="PROXY")
        subject = prefix + force_text(subject)
        from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)
        assigned_to = []
        if project.assigned_to_users:
            [
                assigned_to.append(project_user.first_name + " " + project_user.last_name)
                for project_user in project.assigned_to_users.all()
            ]
        if project.assigned_to_group:
            assigned_to.extend(project.assigned_to_group.all().values_list('name', flat=True))
        reply_to = email_with_site_domain("pj.{}.{}.{}").format(
            request_obj.servicedeskuser.id, request_obj.service_desk_request.id, project.id, schema_name
        )
        reply_to = reply_to.strip().lower()
        ctx = {
            'service_desk_url': service_desk_url,
            'message': message.message,
            'request_name': project.name,
            'priority': importance[project.importance - 1],
            'due_date': project.due_date.strftime('%D'),
            'assigned_to': ' , '.join(assigned_to),
        }
        message = get_template('notification/project_new_reply_email_notification_message.html').render(ctx)
        msg = EmailMessage(
            subject, message, to=(request_obj.servicedeskuser.user_email,), from_email=from_email, reply_to=(reply_to,)
        )
        msg.content_subtype = 'html'
        msg.send()
    else:
        pass


@shared_task
def workflow_new_message_notification(message, workflow, user):
    request_obj = ServiceDeskExternalRequest.objects.filter(workflow=workflow).first()
    if request_obj:
        from django.db import connection

        base_url = settings.SITE_URL.format(connection.schema_name)
        schema_name = connection.schema_name
        importance = ["Low", "Medium", "High"]
        if request_obj.servicedeskuser.is_expire:
            request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
            request_obj.servicedeskuser.is_expire = False
            request_obj.servicedeskuser.save()
        service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
        subject = "You Have a New Message regarding Request No. {}".format(request_obj.service_desk_request.id)
        prefix = "[{name}] ".format(name="PROXY")
        subject = prefix + force_text(subject)
        from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)
        assigned_to = []
        if workflow.assigned_to_users:
            [
                assigned_to.append(workflow_user.first_name + " " + workflow_user.last_name)
                for workflow_user in workflow.assigned_to_users.all()
            ]
        if workflow.assigned_to_group:
            assigned_to.extend(workflow.assigned_to_group.all().values_list('name', flat=True))
        reply_to = email_with_site_domain("wf.{}.{}.{}").format(
            request_obj.servicedeskuser.id, request_obj.service_desk_request.id, workflow.id, schema_name
        )
        reply_to = reply_to.strip().lower()
        ctx = {
            'service_desk_url': service_desk_url,
            'message': message.message,
            'request_name': workflow.name,
            'priority': importance[workflow.importance - 1],
            'due_date': workflow.due_date.strftime('%D'),
            'assigned_to': ' , '.join(assigned_to),
        }
        message = get_template('notification/project_new_reply_email_notification_message.html').render(ctx)
        msg = EmailMessage(
            subject, message, to=(request_obj.servicedeskuser.user_email,), from_email=from_email, reply_to=(reply_to,)
        )
        msg.content_subtype = 'html'
        msg.send()
    else:
        pass


@shared_task
def task_new_message_notification(message, task, user):
    if message.servicedesk_request:
        request_obj = ServiceDeskExternalRequest.objects.filter(
            task=task, service_desk_request=message.servicedesk_request
        ).first()
    else:
        request_obj = ServiceDeskExternalRequest.objects.filter(task=task).first()
    if request_obj:
        from django.db import connection

        base_url = settings.SITE_URL.format(connection.schema_name)
        schema_name = connection.schema_name
        try:
            due_date = task.due_date.strftime('%D')
        except Exception as e:
            print("exception:", e)
            due_date = None
        importance = ["Low", "Medium", "High"]
        if request_obj.servicedeskuser.is_expire:
            request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
            request_obj.servicedeskuser.is_expire = False
            request_obj.servicedeskuser.save()
        service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
        subject = "You Have a New Message regarding Request No. {}".format(request_obj.service_desk_request.id)
        prefix = "[{name}] ".format(name="PROXY")
        subject = prefix + force_text(subject)
        from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)
        assigned_to = []
        if task.assigned_to:
            assigned_to.append(task.assigned_to.first_name + " " + task.assigned_to.last_name)
        if task.assigned_to_group:
            assigned_to.extend(task.assigned_to_group.all().values_list('name', flat=True))
        reply_to = email_with_site_domain("tk.{}.{}.{}").format(
            request_obj.servicedeskuser.id, request_obj.service_desk_request.id, task.id, schema_name
        )
        reply_to = reply_to.strip().lower()
        ctx = {
            'service_desk_url': service_desk_url,
            'message': message.message,
            'request_name': task.name,
            'priority': importance[task.importance - 1],
            'due_date': due_date,
            'assigned_to': ' , '.join(assigned_to),
        }
        cc_email = []
        if ServiceDeskExternalCCUser.objects.filter(message=message).exists():
            [
                cc_email.append(email)
                for email in ServiceDeskExternalCCUser.objects.filter(message=message).values_list('email', flat=True)[
                    ::1
                ]
            ]
        temp = get_template('notification/project_new_reply_email_notification_message.html').render(ctx)
        msg = EmailMessage(
            subject,
            temp,
            to=(request_obj.servicedeskuser.user_email,),
            from_email=from_email,
            reply_to=(reply_to,),
        )
        msg.content_subtype = 'html'
        msg.send()
        for email in cc_email:
            ctx = {
                'message': message.message,
            }
            temp = get_template('notification/cc_email_notification_message.html').render(ctx)
            msg = EmailMessage(
                subject,
                temp,
                to=(email,),
                from_email=from_email,
            )
            if Attachment.objects.filter(message_document=message).exists():
                for attachment_obj in Attachment.objects.filter(message_document=message):
                    msg.attach(attachment_obj.document_name, attachment_obj.document.read())
                    attachment_obj.document.close()
            msg.content_subtype = 'html'
            msg.send()
    else:
        pass


@shared_task
def send_notification_to_servicedeskuser(instance, message_obj, type):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    if instance.servicedeskuser.is_expire:
        instance.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        instance.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
        instance.servicedeskuser.is_expire = False
        instance.servicedeskuser.save()
    service_desk_url = base_url + "/requests/pending-requests/" + str(instance.servicedeskuser.access_token)
    subject = "Request No {} is in Progress!".format(instance.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    subject = prefix + force_text(subject)
    importance = ["Low", "Medium", "High"]
    try:
        due_date = instance.task.due_date.strftime('%D')
    except Exception as e:
        print("exception:", e)
        due_date = None
    assigned_to = []
    if instance.task.assigned_to:
        assigned_to.append(instance.task.assigned_to.first_name + " " + instance.task.assigned_to.last_name)
    if instance.task.assigned_to_group:
        assigned_to.extend(instance.task.assigned_to_group.all().values_list('name', flat=True))
    attachments = Attachment.objects.filter(task=instance.task, is_delete=False).count()
    accept_by = "{} {}".format(instance.created_by.first_name, instance.created_by.last_name)
    schema_name = connection.schema_name
    reply_to = email_with_site_domain("tk.{}.{}.{}").format(
        instance.servicedeskuser.id, instance.service_desk_request.id, instance.task.id, schema_name
    )
    reply_to = reply_to.strip().lower()
    ctx = {
        'service_desk_url': service_desk_url,
        'request_name': instance.task.name,
        'priority': importance[instance.task.importance - 1],
        'due_date': due_date,
        'assigned_to': ' , '.join(assigned_to),
        'attachments': attachments,
        'user_name': instance.servicedeskuser.user_name,
        'company': instance.task.organization,
        'accept_by': accept_by,
        'message': message_obj.message,
        'type': type,
    }
    cc_email = []
    if ServiceDeskExternalCCUser.objects.filter(message=message_obj).exists():
        [
            cc_email.append(email)
            for email in ServiceDeskExternalCCUser.objects.filter(message=message_obj).values_list('email', flat=True)[
                ::1
            ]
        ]
    message = get_template('notification/email_request_converts_to_task_message.html').render(ctx)
    msg = EmailMessage(
        subject,
        message,
        to=(instance.servicedeskuser.user_email,),
        from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
        reply_to=(reply_to,),
    )
    msg.content_subtype = 'html'
    msg.send()
    for email in cc_email:
        ctx = {
            'message': message_obj.message,
        }
        temp = get_template('notification/cc_email_notification_message.html').render(ctx)
        msg = EmailMessage(
            subject,
            temp,
            to=(email,),
            from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
        )
        if Attachment.objects.filter(message_document=message_obj).exists():
            for attachment_obj in Attachment.objects.filter(message_document=message_obj):
                msg.attach(attachment_obj.document_name, attachment_obj.document.read())
                attachment_obj.document.close()
        msg.content_subtype = 'html'
        msg.send()


@shared_task
def project_send_notification_to_servicedeskuser(instance):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    if instance.servicedeskuser.is_expire:
        instance.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        instance.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
        instance.servicedeskuser.is_expire = False
        instance.servicedeskuser.save()
    service_desk_url = base_url + "/requests/pending-requests/" + str(instance.servicedeskuser.access_token)
    subject = "Request No {} is in Progress!".format(instance.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    subject = prefix + force_text(subject)
    importance = ["Low", "Medium", "High"]
    schema_name = connection.schema_name
    due_date = instance.project.due_date.strftime('%D')
    assigned_to = []
    if instance.project.assigned_to_users:
        [
            assigned_to.append(project_user.first_name + " " + project_user.last_name)
            for project_user in instance.project.assigned_to_users.all()
        ]
    if instance.project.assigned_to_group:
        assigned_to.extend(instance.project.assigned_to_group.all().values_list('name', flat=True))
    attachments = Attachment.objects.filter(project=instance.project, is_delete=False).count()
    accept_by = "{} {}".format(instance.created_by.first_name, instance.created_by.last_name)
    reply_to = email_with_site_domain("pj.{}.{}.{}").format(
        instance.servicedeskuser.id, instance.service_desk_request.id, instance.project.id, schema_name
    )
    reply_to = reply_to.strip().lower()
    ctx = {
        'service_desk_url': service_desk_url,
        'request_name': instance.project.name,
        'priority': importance[instance.project.importance - 1],
        'due_date': due_date,
        'assigned_to': ' , '.join(assigned_to),
        'attachments': attachments,
        'user_name': instance.servicedeskuser.user_name,
        'company': instance.project.organization,
        'accept_by': accept_by,
    }
    message = get_template('notification/email_request_converts_to_task_message.html').render(ctx)
    msg = EmailMessage(
        subject,
        message,
        to=(instance.servicedeskuser.user_email,),
        from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
        reply_to=(reply_to,),
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def workflow_send_notification_to_servicedeskuser(instance):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    schema_name = connection.schema_name
    if instance.servicedeskuser.is_expire:
        instance.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        instance.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
        instance.servicedeskuser.is_expire = False
        instance.servicedeskuser.save()
    service_desk_url = base_url + "/requests/pending-requests/" + str(instance.servicedeskuser.access_token)
    subject = "Request No {} is in Progress!".format(instance.service_desk_request.id)
    prefix = "[{name}] ".format(name="PROXY")
    subject = prefix + force_text(subject)
    importance = ["Low", "Medium", "High"]
    due_date = instance.workflow.due_date.strftime('%D')
    assigned_to = []
    if instance.workflow.assigned_to_users:
        [
            assigned_to.append(workflow_user.first_name + " " + workflow_user.last_name)
            for workflow_user in instance.workflow.assigned_to_users.all()
        ]
    if instance.workflow.assigned_to_group:
        assigned_to.extend(instance.workflow.assigned_to_group.all().values_list('name', flat=True))
    attachments = Attachment.objects.filter(workflow=instance.workflow, is_delete=False).count()
    accept_by = "{} {}".format(instance.created_by.first_name, instance.created_by.last_name)
    reply_to = email_with_site_domain("wf.{}.{}.{}").format(
        instance.servicedeskuser.id, instance.service_desk_request.id, instance.workflow.id, schema_name
    )
    reply_to = reply_to.strip().lower()
    ctx = {
        'service_desk_url': service_desk_url,
        'request_name': instance.workflow.name,
        'priority': importance[instance.workflow.importance - 1],
        'due_date': due_date,
        'assigned_to': ' , '.join(assigned_to),
        'attachments': attachments,
        'user_name': instance.servicedeskuser.user_name,
        'company': instance.workflow.organization,
        'accept_by': accept_by,
    }
    message = get_template('notification/email_request_converts_to_task_message.html').render(ctx)
    msg = EmailMessage(
        subject,
        message,
        to=(instance.servicedeskuser.user_email,),
        from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
        reply_to=(reply_to,),
    )
    msg.content_subtype = 'html'
    msg.send()


def document_uplaod_notification_to_servicedeskuser(instance, model, user):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    prefix = "[{name}] ".format(name="PROXY")
    assigned_to = []
    try:
        due_date = instance.due_date.strftime('%D')
    except Exception as e:
        print("exception:", e)
        due_date = None
    importance = ["Low", "Medium", "High"]
    if model == "task":
        attachments = Attachment.objects.filter(task=instance, is_delete=False).count()
        if instance.assigned_to:
            assigned_to.append(instance.assigned_to.first_name + " " + instance.assigned_to.last_name)
        if instance.assigned_to_group:
            assigned_to.extend(instance.assigned_to_group.all().values_list('name', flat=True))
        for request_obj in ServiceDeskExternalRequest.objects.filter(task=instance):
            email_subject = (
                "A new document has been " "uploaded to Request No. " "{}".format(request_obj.service_desk_request.id)
            )
            if request_obj.servicedeskuser.is_expire:
                request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
                request_obj.servicedeskuser.is_expire = False
                request_obj.servicedeskuser.save()
            service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
            email_subject = prefix + force_text(email_subject)
            ctx = {
                'service_desk_url': service_desk_url,
                'priority': importance[instance.importance - 1],
                'assigned_to': ' , '.join(assigned_to),
                'due_date': due_date,
                'attachments': attachments,
                'name': instance.name,
            }
            to_email = request_obj.servicedeskuser.user_email
            from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)

            message = get_template('notification/new_document_email_notification_message.html').render(ctx)
            msg = EmailMessage(
                email_subject,
                message,
                to=(to_email,),
                from_email=from_email,
            )
            msg.content_subtype = 'html'
            msg.send()
        return None
    elif model == "project":
        request_obj = ServiceDeskExternalRequest.objects.filter(project=instance).first()
        email_subject = (
            "A new document has been " "uploaded to Request No. " "{}".format(request_obj.service_desk_request.id)
        )
        if request_obj.servicedeskuser.is_expire:
            request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
            request_obj.servicedeskuser.is_expire = False
            request_obj.servicedeskuser.save()
        service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
        attachments = Attachment.objects.filter(project=instance, is_delete=False).count()
        if instance.assigned_to_users:
            [assigned_to.append(user.first_name + " " + user.last_name) for user in instance.assigned_to_users.all()]
        if instance.assigned_to_group:
            assigned_to.extend(instance.assigned_to_group.all().values_list('name', flat=True))
    else:
        request_obj = ServiceDeskExternalRequest.objects.filter(workflow=instance).first()
        email_subject = (
            "A new document has been " "uploaded to Request No. " "{}".format(request_obj.service_desk_request.id)
        )
        if request_obj.servicedeskuser.is_expire:
            request_obj.servicedeskuser.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
            request_obj.servicedeskuser.expiration_date = timezone.now() + timedelta(7)
            request_obj.servicedeskuser.is_expire = False
            request_obj.servicedeskuser.save()
        service_desk_url = base_url + "/requests/pending-requests/" + str(request_obj.servicedeskuser.access_token)
        attachments = Attachment.objects.filter(workflow=instance, is_delete=False).count()
        if instance.assigned_to_users:
            [assigned_to.append(user.first_name + " " + user.last_name) for user in instance.assigned_to_users.all()]
        if instance.assigned_to_group:
            assigned_to.extend(instance.assigned_to_group.all().values_list('name', flat=True))
    email_subject = prefix + force_text(email_subject)
    ctx = {
        'service_desk_url': service_desk_url,
        'priority': importance[instance.importance - 1],
        'assigned_to': ' , '.join(assigned_to),
        'due_date': due_date,
        'attachments': attachments,
        'name': instance.name,
    }
    to_email = request_obj.servicedeskuser.user_email
    from_email = '{} {}<{}>'.format(user.first_name, user.last_name, settings.DEFAULT_FROM_EMAIL)

    message = get_template('notification/new_document_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        email_subject,
        message,
        to=(to_email,),
        from_email=from_email,
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def request_submit_notification(request, user, model_obj, model):
    from django.db import connection

    base_url = settings.SITE_URL.format(connection.schema_name)
    company = request.user_information.organization
    if request.user_information.is_expire:
        request.user_information.access_token = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        request.user_information.expiration_date = timezone.now() + timedelta(7)
        request.user_information.is_expire = False
        request.user_information.save()
    assigned_to = []
    if model in ["project", "workflow"]:
        if model_obj.assigned_to_users:
            [assigned_to.append(user.first_name + " " + user.last_name) for user in model_obj.assigned_to_users.all()]
        if model_obj.assigned_to_group:
            assigned_to.extend(model_obj.assigned_to_group.all().values_list('name', flat=True))
    else:
        if model_obj.assigned_to:
            assigned_to.append(model_obj.assigned_to.first_name + " " + model_obj.assigned_to.last_name)
        if model_obj.assigned_to_group:
            assigned_to.extend(model_obj.assigned_to_group.all().values_list('name', flat=True))
    importance = ["Low", "Medium", "High"]
    try:
        import dateutil.parser as dt_parse

        due_date = dt_parse.parse(request.requested_due_date).strftime('%D')
    except Exception as e:
        print("exception:", e)
        due_date = None
    service_desk_url = base_url + "/requests/pending-requests/" + str(request.user_information.access_token)
    ctx = {
        "user": str(user.first_name + " " + user.last_name),
        "company": company,
        "request_name": request.subject,
        "priority": importance[request.request_priority - 1],
        "assign_to": ' , '.join(assigned_to),
        "due_date": due_date,
        "notes": request.description,
        'service_desk_url': service_desk_url,
    }
    subject = "You have a new request from {} !".format(company)
    prefix = "[{name}] ".format(name="PROXY")
    subject = prefix + force_text(subject)
    message = get_template('notification/internal_request_submit_email_notification_message.html').render(ctx)
    msg = EmailMessage(
        subject,
        message,
        to=(request.user_information.user_email,),
        from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
    )
    msg.content_subtype = 'html'
    msg.send()


@shared_task
def privilege_log_history(instance, category):
    created_at = instance.modified_at.date()
    changed_by = instance.last_modified_by
    users_list = []
    privilege_log_data = []
    privilege = []
    if instance.attorney_client_privilege:
        privilege.append("Attorney Client")
    if instance.work_product_privilege:
        privilege.append("Work Product")
    if instance.confidential_privilege:
        privilege.append("Confidential")
    if category == "task":
        if instance.assigned_to and privilege:
            Privilage_Change_Log.objects.create(
                category_type=category,
                task=instance,
                team_member=instance.assigned_to,
                new_privilege=privilege,
                changed_at=created_at,
                changed_by=changed_by,
            )
    elif category == "project":
        if instance.assigned_to_users.all().exists() and privilege:
            [
                users_list.append(project_user)
                for project_user in instance.assigned_to_users.all()
                if project_user not in users_list
            ]
            [
                privilege_log_data.append(
                    Privilage_Change_Log(
                        category_type=category,
                        project=instance,
                        team_member=user,
                        new_privilege=privilege,
                        changed_at=created_at,
                        changed_by=changed_by,
                    )
                )
                for user in users_list
            ]
            Privilage_Change_Log.objects.bulk_create(privilege_log_data)
    else:
        if instance.assigned_to_users.all().exists() and privilege:
            [
                users_list.append(workflow_user)
                for workflow_user in instance.assigned_to_users.all()
                if workflow_user not in users_list
            ]
            [
                privilege_log_data.append(
                    Privilage_Change_Log(
                        category_type=category,
                        workflow=instance,
                        team_member=user,
                        new_privilege=privilege,
                        changed_at=created_at,
                        changed_by=changed_by,
                    )
                )
                for user in users_list
            ]
            Privilage_Change_Log.objects.bulk_create(privilege_log_data)


@shared_task
def active_tag_log_history(instance, category):
    tag_log_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, project=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.project_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    elif category == "workflow":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, workflow=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.workflow_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    else:
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, task=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.task_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)


@shared_task
def update_tag_log_history(instance, category):
    tag_log_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, project=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.project_tags.all()
            if not TagChangeLog.objects.filter(
                project=instance, category_type=category, changed_at=changed_at, tag_reference=tag_obj, new=1
            ).exists()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    elif category == "workflow":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, workflow=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.workflow_tags.all()
            if not TagChangeLog.objects.filter(
                workflow=instance, category_type=category, changed_at=changed_at, tag_reference=tag_obj, new=1
            ).exists()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    else:
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, new=1, task=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.task_tags.all()
            if not TagChangeLog.objects.filter(
                task=instance, category_type=category, changed_at=changed_at, tag_reference=tag_obj, new=1
            ).exists()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)


@shared_task
def completed_tag_log_history(instance, category):
    tag_log_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, completed=1, project=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.project_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    elif category == "workflow":
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category,
                    tag_reference=tag_obj,
                    completed=1,
                    workflow=instance,
                    changed_at=changed_at,
                )
            )
            for tag_obj in instance.workflow_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)
    else:
        [
            tag_log_data.append(
                TagChangeLog(
                    category_type=category, tag_reference=tag_obj, completed=1, task=instance, changed_at=changed_at
                )
            )
            for tag_obj in instance.task_tags.all()
        ]
        TagChangeLog.objects.bulk_create(tag_log_data)


@shared_task
def active_group_workload_history(instance, category):
    group_workload_log_data = []
    work_productivity_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category, new=1, work_group=group_obj, project=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, work_group=group_obj, new=1, project=instance, created_on=changed_at
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category, work_group=group_obj, new=1, workflow=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, work_group=group_obj, new=1, workflow=instance, created_on=changed_at
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category, work_group=group_obj, new=1, task=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, work_group=group_obj, new=1, task=instance, created_on=changed_at
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)


@shared_task
def complete_group_workload_history(instance, category):
    group_workload_log_data = []
    work_productivity_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category,
                        work_group=group_obj,
                        completed=1,
                        project=instance,
                        changed_at=changed_at,
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category,
                        work_group=group_obj,
                        completed=1,
                        project=instance,
                        created_on=changed_at,
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category,
                        work_group=group_obj,
                        completed=1,
                        workflow=instance,
                        changed_at=changed_at,
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category,
                        work_group=group_obj,
                        completed=1,
                        workflow=instance,
                        created_on=changed_at,
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        [
            (
                group_workload_log_data.append(
                    GroupWorkLoadLog(
                        category_type=category, work_group=group_obj, completed=1, task=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, work_group=group_obj, completed=1, task=instance, created_on=changed_at
                    )
                ),
            )
            for group_obj in instance.assigned_to_group.all()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)


@shared_task
def update_group_workload_history(instance, category):
    group_workload_log_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            group_workload_log_data.append(
                GroupWorkLoadLog(
                    category_type=category, work_group=group_obj, new=1, project=instance, changed_at=changed_at
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not GroupWorkLoadLog.objects.filter(
                project=instance, category_type=category, changed_at=changed_at, work_group=group_obj, new=1
            ).exists()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
    elif category == "workflow":
        [
            group_workload_log_data.append(
                GroupWorkLoadLog(
                    category_type=category, work_group=group_obj, new=1, workflow=instance, changed_at=changed_at
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not GroupWorkLoadLog.objects.filter(
                workflow=instance, category_type=category, changed_at=changed_at, work_group=group_obj, new=1
            ).exists()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)
    else:
        [
            group_workload_log_data.append(
                GroupWorkLoadLog(
                    category_type=category, work_group=group_obj, new=1, task=instance, changed_at=changed_at
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not GroupWorkLoadLog.objects.filter(
                task=instance, category_type=category, changed_at=changed_at, work_group=group_obj, new=1
            ).exists()
        ]
        GroupWorkLoadLog.objects.bulk_create(group_workload_log_data)


@shared_task
def team_member_workload_history(instance, category):
    team_member_workload_log_data = []
    work_productivity_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            (
                team_member_workload_log_data.append(
                    TeamMemberWorkLoadLog(
                        category_type=category, team_member=user_obj, new=1, project=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, team_member=user_obj, new=1, project=instance, created_on=changed_at
                    )
                ),
            )
            for user_obj in instance.assigned_to_users.all()
        ]
        TeamMemberWorkLoadLog.objects.bulk_create(team_member_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            (
                team_member_workload_log_data.append(
                    TeamMemberWorkLoadLog(
                        category_type=category, team_member=user_obj, new=1, workflow=instance, changed_at=changed_at
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category, team_member=user_obj, new=1, workflow=instance, created_on=changed_at
                    )
                ),
            )
            for user_obj in instance.assigned_to_users.all()
        ]
        TeamMemberWorkLoadLog.objects.bulk_create(team_member_workload_log_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        TeamMemberWorkLoadLog.objects.create(
            category_type=category, team_member=instance.assigned_to, new=1, task=instance, changed_at=changed_at
        )
        WorkProductivityLog.objects.create(
            category_type=category, team_member=instance.assigned_to, new=1, task=instance, created_on=changed_at
        )


@shared_task
def update_team_member_workload_history(instance, category):
    team_member_workload_log_data = []
    changed_at = instance.modified_at.date()
    if category == "project":
        [
            team_member_workload_log_data.append(
                TeamMemberWorkLoadLog(
                    category_type=category, team_member=user_obj, new=1, project=instance, changed_at=changed_at
                )
            )
            for user_obj in instance.assigned_to_users.all()
            if not TeamMemberWorkLoadLog.objects.filter(
                category_type=category, team_member=user_obj, new=1, project=instance, changed_at=changed_at
            ).exists()
        ]
        TeamMemberWorkLoadLog.objects.bulk_create(team_member_workload_log_data)
    elif category == "workflow":
        [
            team_member_workload_log_data.append(
                TeamMemberWorkLoadLog(
                    category_type=category, team_member=user_obj, new=1, workflow=instance, changed_at=changed_at
                )
            )
            for user_obj in instance.assigned_to_users.all()
            if not TeamMemberWorkLoadLog.objects.filter(
                category_type=category, team_member=user_obj, new=1, workflow=instance, changed_at=changed_at
            ).exists()
        ]
        TeamMemberWorkLoadLog.objects.bulk_create(team_member_workload_log_data)
    else:
        TeamMemberWorkLoadLog.objects.get_or_create(
            category_type=category, team_member=instance.assigned_to, new=1, task=instance, changed_at=changed_at
        )


@shared_task
def completion_workLog(instance, category):
    complete_worklog_data = []
    created_on = instance.created_at.date()
    completed_on = instance.modified_at.date()
    completion_time = (completed_on - created_on).days + 1
    work_productivity_data = []
    if category == "project":
        [
            (
                complete_worklog_data.append(
                    CompletionLog(
                        category_type=category,
                        team_member=user_obj,
                        completion_time=completion_time,
                        project=instance,
                        created_on=created_on,
                        completed_on=completed_on,
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category,
                        team_member=user_obj,
                        completed=1,
                        project=instance,
                        created_on=completed_on,
                    )
                ),
            )
            for user_obj in instance.assigned_to_users.all()
        ]
        CompletionLog.objects.bulk_create(complete_worklog_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            (
                complete_worklog_data.append(
                    CompletionLog(
                        category_type=category,
                        team_member=user_obj,
                        completion_time=completion_time,
                        workflow=instance,
                        created_on=created_on,
                        completed_on=completed_on,
                    )
                ),
                work_productivity_data.append(
                    WorkProductivityLog(
                        category_type=category,
                        team_member=user_obj,
                        completed=1,
                        workflow=instance,
                        created_on=completed_on,
                    )
                ),
            )
            for user_obj in instance.assigned_to_users.all()
        ]
        CompletionLog.objects.bulk_create(complete_worklog_data)
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        CompletionLog.objects.create(
            category_type=category,
            team_member=instance.assigned_to,
            completion_time=completion_time,
            task=instance,
            created_on=created_on,
            completed_on=completed_on,
        )
        WorkProductivityLog.objects.create(
            category_type=category,
            team_member=instance.assigned_to,
            completed=1,
            task=instance,
            created_on=completed_on,
        )


@shared_task
def update_work_productivity_log(instance, category):
    work_productivity_data = []
    created_on = instance.modified_at.date()
    if category == "project":
        [
            work_productivity_data.append(
                WorkProductivityLog(
                    category_type=category, team_member=user_obj, new=1, project=instance, created_on=created_on
                )
            )
            for user_obj in instance.assigned_to_users.all()
            if not WorkProductivityLog.objects.filter(
                category_type=category, team_member=user_obj, new=1, project=instance, created_on=created_on
            ).exists()
        ]
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            work_productivity_data.append(
                WorkProductivityLog(
                    category_type=category, team_member=user_obj, new=1, workflow=instance, created_on=created_on
                )
            )
            for user_obj in instance.assigned_to_users.all()
            if not WorkProductivityLog.objects.filter(
                category_type=category, team_member=user_obj, new=1, workflow=instance, created_on=created_on
            ).exists()
        ]
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        WorkProductivityLog.objects.get_or_create(
            category_type=category, team_member=instance.assigned_to, new=1, task=instance, created_on=created_on
        )


@shared_task
def update_group_work_productivity_log(instance, category):
    work_productivity_data = []
    created_on = instance.modified_at.date()
    if category == "project":
        [
            work_productivity_data.append(
                WorkProductivityLog(
                    category_type=category, work_group=group_obj, new=1, project=instance, created_on=created_on
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not WorkProductivityLog.objects.filter(
                category_type=category, work_group=group_obj, new=1, project=instance, created_on=created_on
            ).exists()
        ]
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    elif category == "workflow":
        [
            work_productivity_data.append(
                WorkProductivityLog(
                    category_type=category, work_group=group_obj, new=1, workflow=instance, created_on=created_on
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not WorkProductivityLog.objects.filter(
                category_type=category, work_group=group_obj, new=1, workflow=instance, created_on=created_on
            ).exists()
        ]
        WorkProductivityLog.objects.bulk_create(work_productivity_data)
    else:
        [
            work_productivity_data.append(
                WorkProductivityLog(
                    category_type=category, work_group=group_obj, new=1, task=instance, created_on=created_on
                )
            )
            for group_obj in instance.assigned_to_group.all()
            if not WorkProductivityLog.objects.filter(
                category_type=category, work_group=group_obj, new=1, task=instance, created_on=created_on
            ).exists()
        ]
        WorkProductivityLog.objects.bulk_create(work_productivity_data)


def complete_dependent_task(instance, user):
    today_date = datetime.datetime.utcnow()
    for task_obj in Task.objects.filter(prior_task=instance).exclude(status__in=[2, 3, 4]):
        task_obj.status = 2
        task_obj.start_date = today_date
        task_obj.save()
        AuditHistoryCreate("task", task_obj.id, user, "In Progress at")


@shared_task
def share_document_to_user(attachment_obj, emails, user):
    task_user_emails = []
    task_obj = attachment_obj.task
    task_user_emails.append(task_obj.created_by.email)
    if task_obj.assigned_to:
        task_user_emails.append(task_obj.assigned_to.email)
    if task_obj.assigned_to_group.exists():
        for group in task_obj.assigned_to_group.all():
            [task_user_emails.append(group_member.email) for group_member in group.group_members.all()]
    task_user_emails = list(set(task_user_emails))
    for email in emails:
        if email in task_user_emails:
            user_name = User.objects.filter(email__iexact=user.email, company=user.company).first()
            subject = "{} {} has shared a document " "with you.".format(user.first_name, user.last_name)
            ctx = {
                "share_to": user_name.first_name,
                "share_by": "{} {}".format(user.first_name, user.last_name),
                "document_name": attachment_obj.document_name,
                "task_name": attachment_obj.task.name,
            }
            message = get_template('notification/share_document_to_proxy_user_message.html').render(ctx)
        else:
            subject = "A private document has been shared with you!"
            ctx = {"document_name": attachment_obj.document_name}
            message = get_template('notification/share_document_to_external_user_message.html').render(ctx)
        prefix = "[{name}] ".format(name="PROXY")
        subject = prefix + force_text(subject)
        msg = EmailMessage(
            subject,
            message,
            to=(email,),
            from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
        )
        msg.attach(attachment_obj.document_name, attachment_obj.document.read())
        msg.content_subtype = 'html'
        msg.send()
        attachment_obj.document.close()


@shared_task
def task_new_internal_message_notification(task_obj, message_obj):
    notification_type_obj = NotificationType.objects.filter(slug="task_new_message").first()
    if notification_type_obj:
        from django.db import connection

        email_users = []
        site_url = settings.SITE_URL.format(connection.schema_name)
        notified_url = site_url + "/main/projects/tasks/" + str(task_obj.pk)
        in_app_notification_url = "projects/tasks/" + str(task_obj.pk)
        notification_message = "There are updates to the " "discussion in {}".format(task_obj.name)
        subject = "New reply to {}.".format(task_obj.name)
        users = []
        if task_obj.created_by:
            users.append(task_obj.created_by)
        if task_obj.assigned_to:
            users.append(task_obj.assigned_to)
        if task_obj.assigned_to_group.exists():
            for group in task_obj.assigned_to_group.all():
                [users.append(group_member) for group_member in group.group_members.all()]
        users = list(set(users))
        if message_obj.created_by_user in users:
            users.remove(message_obj.created_by_user)
        for user in users:
            if UserNotificationSetting.objects.filter(
                user=user, notification_type=notification_type_obj, in_app_notification=True
            ).exists():
                data_dict = {
                    "title": notification_message,
                    "message_body": notification_message,
                    "notification_type": notification_type_obj,
                    "user": user,
                    "notification_url": in_app_notification_url,
                    "status": 1,
                }
                notification = Notification.objects.create(**data_dict)
                notification.notify_ws_clients()
            if UserNotificationSetting.objects.filter(
                user=user, notification_type=notification_type_obj, email_notification=True
            ).exists():
                email_users.append({'email': user.email, 'user': user})
        if message_obj.message:
            message = message_obj.message
        else:
            message = None
        reply_to = email_with_site_domain("task_{}").format(task_obj.pk, connection.schema_name)
        for email_user in email_users:
            ctx = {
                "to_user": email_user['user'].first_name,
                "task_url": notified_url,
                "task_name": task_obj.name,
                "message": message,
            }
            temp = get_template('notification/email_notification_task_internal_message.html').render(ctx)
            prefix = "[{name}] ".format(name="PROXY")
            subject = prefix + force_text(subject)
            msg = EmailMessage(
                subject,
                temp,
                to=(email_user['email'],),
                from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
                reply_to=(reply_to,),
            )
            if Attachment.objects.filter(message_document=message_obj).exists():
                for attachment_obj in Attachment.objects.filter(message_document=message_obj):
                    msg.attach(attachment_obj.document_name, attachment_obj.document.read())
                    attachment_obj.document.close()
            msg.content_subtype = 'html'
            msg.send()


@shared_task
def new_internal_message_notification(instance, model, message_obj):
    from django.db import connection

    if model == "project":
        notification_type_obj = NotificationType.objects.filter(slug="project_new_message").first()
        site_url = settings.SITE_URL.format(connection.schema_name)
        notified_url = site_url + "/main/projects/" + str(instance.pk)
        in_app_notification_url = "projects/" + str(instance.pk)
        reply_to = email_with_site_domain("project_{}").format(instance.pk, connection.schema_name)
    elif model == "workflow":
        notification_type_obj = NotificationType.objects.filter(slug="workflow_new_message").first()
        site_url = settings.SITE_URL.format(connection.schema_name)
        notified_url = site_url + "/main/projects/workflow/" + str(instance.pk)
        in_app_notification_url = "projects/workflow/" + str(instance.pk)
        reply_to = email_with_site_domain("workflow_{}").format(instance.pk, connection.schema_name)
    else:
        return None
    if notification_type_obj:
        from django.db import connection

        email_users = []
        notification_message = "There are updates to the " "discussion in {}".format(instance.name)
        subject = "New reply to {}.".format(instance.name)
        users = []
        if instance.created_by:
            users.append(instance.created_by)
        if instance.owner:
            users.append(instance.owner)
        if instance.assigned_to_users.exists():
            [users.append(assignee) for assignee in instance.assigned_to_users.all()]
        if instance.assigned_to_group.exists():
            for group in instance.assigned_to_group.all():
                [users.append(group_member) for group_member in group.group_members.all()]
        users = list(set(users))
        if message_obj.created_by_user in users:
            users.remove(message_obj.created_by_user)
        if message_obj.message:
            message = message_obj.message
        else:
            message = None
        for user in users:
            if UserNotificationSetting.objects.filter(
                user=user, notification_type=notification_type_obj, in_app_notification=True
            ).exists():
                data_dict = {
                    "title": notification_message,
                    "message_body": notification_message,
                    "notification_type": notification_type_obj,
                    "user": user,
                    "notification_url": in_app_notification_url,
                    "status": 1,
                }
                notification = Notification.objects.create(**data_dict)
                notification.notify_ws_clients()
            if UserNotificationSetting.objects.filter(
                user=user, notification_type=notification_type_obj, email_notification=True
            ).exists():
                email_users.append({'email': user.email, 'user': user})
        for email_user in email_users:
            ctx = {
                "to_user": email_user['user'].first_name,
                "redirection_url": notified_url,
                "name": instance.name,
                "model": model,
                "message": message,
            }
            temp = get_template('notification/email_notification_of_internal_message.html').render(ctx)
            prefix = "[{name}] ".format(name="PROXY")
            subject = prefix + force_text(subject)
            msg = EmailMessage(
                subject,
                temp,
                to=(email_user['email'],),
                reply_to=(reply_to,),
                from_email='{}<{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL),
            )
            if Attachment.objects.filter(message_document=message_obj).exists():
                for attachment_obj in Attachment.objects.filter(message_document=message_obj):
                    msg.attach(attachment_obj.document_name, attachment_obj.document.read())
                    attachment_obj.document.close()
            msg.content_subtype = 'html'
            msg.send()


def task_message_inbound_webhook(data, inbound_email):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    user = User.objects.filter(email=from_email, is_delete=False).last()
    try:
        task_id = int(inbound_email.split("@")[0].split("_")[1])
    except Exception as e:
        print("exception:", e)
        return JsonResponse({'status': 'ok'})
    if user:
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
            t_qset = Task.objects.filter(q_obj).distinct('id')
        elif GroupAndPermission.objects.filter(
            group=group, company=company, has_permission=True, permission__slug='task_task-view'
        ).exists():
            t_qset = Task.objects.filter(
                Q(organization=company),
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to_group__group_members=user),
            ).distinct('id')
        else:
            return JsonResponse({'status': 'ok'})
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='task',
            permission__slug='task_view-archived',
            has_permission=True,
        ).exists():
            t_qset = t_qset.exclude(status__in=[3, 4])
        task_obj = t_qset.filter(id=task_id).first()
        if task_obj:
            if postmark_obj.has_attachments and task_obj.status not in [3, 4]:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        task=task_obj, message=text, created_by_user=user, is_internal_message=True
                    )
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        task=task_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                else:
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        task=task_obj, message=None, created_by_user=user, is_internal_message=True
                    )
                AuditHistoryCreate("task", task_obj.id, user, "Document Uploaded at")
                for attachment in postmark_obj.attachments:
                    save_attachment_from_email(
                        attachment=attachment, instance_target_to=task_obj, user=user, message_document=message_obj
                    )

                task_new_internal_message_notification.delay(task_obj, message_obj)
            else:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        task=task_obj, message=text, created_by_user=user, is_internal_message=True
                    )
                    task_new_internal_message_notification.delay(task_obj, message_obj)
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        task=task_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                    task_new_internal_message_notification.delay(task_obj, message_obj)
                else:
                    return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'ok'})


def workflow_message_inbound_webhook(data, inbound_email):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    user = User.objects.filter(email=from_email, is_delete=False).last()
    try:
        workflow_id = int(inbound_email.split("@")[0].split("_")[1])
    except Exception as e:
        print("exception:", e)
        return JsonResponse({'status': 'ok'})
    if user:
        company = user.company
        group = user.group
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
            return JsonResponse({'status': 'ok'})
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='workflow',
            permission__slug='workflow_view-archived',
            has_permission=True,
        ).exists():
            w_qset = w_qset.exclude(status__in=[2, 3])
        workflow_obj = w_qset.filter(id=workflow_id).first()
        if workflow_obj:
            if postmark_obj.has_attachments and workflow_obj.status not in [2, 3]:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        workflow=workflow_obj, message=text, created_by_user=user, is_internal_message=True
                    )
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        workflow=workflow_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                else:
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        workflow=workflow_obj, message=None, created_by_user=user, is_internal_message=True
                    )
                AuditHistoryCreate("workflow", workflow_obj.id, user, "Document Uploaded at")
                new_internal_message_notification.delay(workflow_obj, "workflow", message_obj)
                for attachment in postmark_obj.attachments:
                    save_attachment_from_email(
                        attachment=attachment, instance_target_to=workflow_obj, user=user, message_document=message_obj
                    )

            else:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=text, workflow=workflow_obj, created_by_user=user, is_internal_message=True
                    )
                    new_internal_message_notification.delay(workflow_obj, "workflow", message_obj)
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        workflow=workflow_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                    new_internal_message_notification.delay(workflow_obj, "workflow", message_obj)
                else:
                    return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'ok'})


def project_message_inbound_webhook(data, inbound_email):
    postmark_obj = PostmarkInbound(json=data)
    from_email = postmark_obj.sender.get('Email').lower().strip()
    user = User.objects.filter(email=from_email, is_delete=False).last()
    try:
        project_id = int(inbound_email.split("@")[0].split("_")[1])
    except Exception as e:
        print("exception:", e)
        return JsonResponse({'status': 'ok'})
    if user:
        company = user.company
        group = user.group
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
            return JsonResponse({'status': 'ok'})
            pass
        if not GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category='project',
            permission__slug='project_view-archived',
            has_permission=True,
        ).exists():
            p_qset = p_qset.exclude(status__in=[2, 3])
        project_obj = p_qset.filter(id=project_id).first()
        if project_obj:
            if postmark_obj.has_attachments and project_obj.status not in [2, 3]:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        project=project_obj, message=text, created_by_user=user, is_internal_message=True
                    )
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        project=project_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                else:
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        project=project_obj, message=None, created_by_user=user, is_internal_message=True
                    )
                AuditHistoryCreate("project", project_obj.id, user, "Document Uploaded at")
                new_internal_message_notification.delay(project_obj, "project", message_obj)
                for attachment in postmark_obj.attachments:
                    save_attachment_from_email(
                        attachment=attachment, instance_target_to=project_obj, user=user, message_document=message_obj
                    )

            else:
                if postmark_obj.source['StrippedTextReply'].strip():
                    text = postmark_obj.source['StrippedTextReply'].strip()
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=text, project=project_obj, created_by_user=user, is_internal_message=True
                    )
                    new_internal_message_notification.delay(project_obj, "project", message_obj)
                elif postmark_obj.text_body.strip():
                    message_obj = ServiceDeskRequestMessage.objects.create(
                        message=postmark_obj.text_body.strip(),
                        project=project_obj,
                        created_by_user=user,
                        is_internal_message=True,
                    )
                    new_internal_message_notification.delay(project_obj, "project", message_obj)
                else:
                    return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'ok'})


def save_attachment_from_email(
    attachment,
    instance_target_to,
    user=None,
    uploaded_by=None,
    message_document=None,
    organization=None,
    *args,
    **kwargs,
):
    try:
        if not organization:
            organization = instance_target_to.organization
        local_path = '/tmp/'
        attachment.download(local_path)
        name = attachment.name().split('.')[-1].lower()
        if name in [
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
        ]:
            content_type = ContentType.objects.get_for_model(model=instance_target_to._meta.model)
            attachment_obj = Attachment(
                content_type=content_type,
                object_id=instance_target_to.pk,
                organization=organization,
                created_by=user,
                uploaded_by=uploaded_by,
                message_document=message_document,
            )
            random_doc_name = get_random_string(20) + "." + name
            with open(local_path + attachment.name(), 'rb') as f:
                attachment_obj.document_name = attachment.name()
                attachment_obj.document.save(random_doc_name, File(f))
            attachment_obj.save()

            AuditHistoryCreate("attachment", attachment_obj.id, user, "Date uploaded:")
            document_associate_history(
                "attachment",
                attachment_obj.id,
                instance_target_to.name,
                f"Associated {instance_target_to._meta.model.__name__}",
                user,
            )

            import os

            os.remove(local_path + attachment.name())
    except Exception:
        logging.exception(
            f'Error: Postmark{instance_target_to._meta.model.__name__}WebHook',
        )
