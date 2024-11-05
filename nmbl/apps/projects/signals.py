from datetime import timedelta

from authentication.models import User
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save, pre_delete, pre_save
from django.utils.timezone import now
from projects.tasks import (
    project_change_user,
    task_change_user,
    workflow_change_user,
    workgroup_add_user,
    workgroup_remove_user,
)

from .helpers import (
    AuditHistoryCreate,
    audit_due_date_history,
    audit_importance_history,
    privilege_log_history,
    project_assigned_notification,
    project_removed_notification,
    task_assigned_notification,
    task_assigned_to_group_notification,
    update_team_member_workload_history,
    update_work_productivity_log,
    workflow_assigned_notification,
    workflow_removed_notification,
)
from .models import Attachment, Project, Task, Workflow, WorkGroup, WorkGroupMember


def task_pre_save(sender, instance, *args, **kwargs):
    if instance.id:
        # If Task is updated then save old data
        PRIVILEGE_CHANGE = False
        old_instance = Task.objects.filter(pk=instance.id).last()
        if old_instance:
            pre_save_data = {}
            if old_instance.workflow:
                pre_save_data['workflow_id'] = old_instance.workflow.id
            if old_instance.assigned_to:
                pre_save_data['assigned_to_id'] = old_instance.assigned_to.id
            instance.pre_save_data = pre_save_data
            if old_instance.due_date != instance.due_date:
                instance.old_due_date = old_instance.due_date
                audit_due_date_history(
                    "task",
                    instance.id,
                    instance.last_modified_by,
                    "Due Date changed",
                    old_instance.due_date,
                    instance.due_date,
                )
                instance.is_email_notified = False
            if old_instance.importance != instance.importance:
                audit_importance_history(
                    "task", instance.id, instance.last_modified_by, "Changed to", instance.importance
                )
            if old_instance.description != instance.description:
                AuditHistoryCreate("task", instance.id, instance.last_modified_by, "Notes were Updated by")
            if old_instance.workflow != instance.workflow:
                if instance.workflow:
                    AuditHistoryCreate(
                        "task", instance.id, instance.last_modified_by, "Added to", instance.workflow.name
                    )
                instance.prior_task = None
                instance.after_task = None
            if old_instance.assigned_to != instance.assigned_to:
                instance.is_assignee_changed = True
                update_work_productivity_log.delay(instance, "task")
                task_assigned_notification(instance)
                update_team_member_workload_history.delay(instance, "task")
                if (
                    old_instance.work_product_privilege != instance.work_product_privilege
                    or old_instance.confidential_privilege != instance.confidential_privilege
                    or old_instance.attorney_client_privilege != instance.attorney_client_privilege
                ):
                    PRIVILEGE_CHANGE = True
                    privilege_log_history.delay(instance, "task")
                if not PRIVILEGE_CHANGE and (
                    instance.attorney_client_privilege
                    or instance.work_product_privilege
                    or instance.confidential_privilege
                ):
                    PRIVILEGE_CHANGE = True
                    privilege_log_history.delay(instance, "task")
            if not PRIVILEGE_CHANGE and (
                old_instance.work_product_privilege != instance.work_product_privilege
                or old_instance.confidential_privilege != instance.confidential_privilege
                or old_instance.attorney_client_privilege != instance.attorney_client_privilege
            ):
                privilege_log_history.delay(instance, "task")
            if old_instance.status != instance.status:
                status_list = [
                    "Re-activated by",
                    "In Progress at",
                    "Marked Completed at",
                    "Archived at",
                    "External Request at",
                    "External Update at",
                    "Advise at",
                    "Analyze at",
                    "Approve at",
                    "Brief at",
                    "Closing at",
                    "Communicate at",
                    "Coordinate at",
                    "Deposition at",
                    "Diligence at",
                    "Discovery at",
                    "Document at",
                    "Draft at",
                    "Execute at",
                    "Fact Gathering at",
                    "File at",
                    "File Management at",
                    "Hearing at",
                    "Investigate at",
                    "Negotiate at",
                    "On Hold at",
                    "Plan at",
                    "Pleading at",
                    "Prepare at",
                    "Research at",
                    "Review at",
                    "Revise at",
                    "Settle at",
                    "Structure at",
                ]
                AuditHistoryCreate(
                    "task", instance.id, instance.last_modified_by, status_list[int(instance.status) - 1]
                )
        if old_instance and (
            old_instance.assigned_to != instance.assigned_to
            or instance.assigned_to_group.all() != old_instance.assigned_to_group.all()
            or old_instance.status != instance.status
            or instance.is_private != old_instance.is_private
        ):
            task_change_user(instance)


def create_task_notification(sender, instance, created, **kwargs):
    if created and instance.assigned_to:
        task_assigned_notification(instance)


def assigned_to_users_changed(sender, **kwargs):
    action = kwargs.get('action')
    project = kwargs.get('instance')
    if action == 'post_add':
        project.is_assignee_changed = True
        for user_id in kwargs.get('pk_set'):
            project_assigned_notification(project, User.objects.get(pk=user_id))
    if action == 'post_remove':
        project.is_assignee_changed = True
        for user_id in kwargs.get('pk_set'):
            project_removed_notification(project, User.objects.get(pk=user_id))


def assigned_to_users_workflow(sender, **kwargs):
    action = kwargs.get('action')
    workflow = kwargs.get('instance')
    if action == 'post_add':
        workflow.is_assignee_changed = True
        for user_id in kwargs.get('pk_set'):
            workflow_assigned_notification(workflow, User.objects.get(pk=user_id))
    if action == 'post_remove':
        workflow.is_assignee_changed = True
        for user_id in kwargs.get('pk_set'):
            workflow_removed_notification(workflow, User.objects.get(pk=user_id))


def project_due_date_change(sender, instance, *args, **kwargs):
    if instance:
        old_instance = Project.objects.filter(pk=instance.id).last()
        if old_instance and old_instance.due_date != instance.due_date:
            instance.old_due_date = old_instance.due_date
            audit_due_date_history(
                "project",
                instance.id,
                instance.last_modified_by,
                "Due Date changed",
                old_instance.due_date,
                instance.due_date,
            )
            instance.is_email_notified = False
        if old_instance and old_instance.importance != instance.importance:
            audit_importance_history(
                "project", instance.id, instance.last_modified_by, "Changed to", instance.importance
            )
        if old_instance and old_instance.description != instance.description:
            AuditHistoryCreate("project", instance.id, instance.last_modified_by, "Notes were Updated by")
        if old_instance and (
            old_instance.work_product_privilege != instance.work_product_privilege
            or old_instance.confidential_privilege != instance.confidential_privilege
            or old_instance.attorney_client_privilege != instance.attorney_client_privilege
        ):
            privilege_log_history.delay(instance, "project")
        if old_instance:
            if old_instance and (
                old_instance.owner != instance.owner
                or old_instance.assigned_to_users.all() != instance.assigned_to_users.all()
                or instance.assigned_to_group.all() != old_instance.assigned_to_group.all()
                or old_instance.status != instance.status
            ):
                project_change_user(instance)


def workflow_due_date_change(sender, instance, *args, **kwargs):
    if instance:
        old_instance = Workflow.objects.filter(pk=instance.id).last()
        if old_instance and old_instance.due_date != instance.due_date:
            instance.old_due_date = old_instance.due_date
            audit_due_date_history(
                "workflow",
                instance.id,
                instance.last_modified_by,
                "Due Date changed",
                old_instance.due_date,
                instance.due_date,
            )
            instance.is_email_notified = False
        if old_instance and old_instance.importance != instance.importance:
            audit_importance_history(
                "workflow", instance.id, instance.last_modified_by, "Changed to", instance.importance
            )
        if old_instance and old_instance.description != instance.description:
            AuditHistoryCreate("workflow", instance.id, instance.last_modified_by, "Notes were Updated by")
        if old_instance and old_instance.project != instance.project:
            if instance.project:
                AuditHistoryCreate(
                    "workflow", instance.id, instance.last_modified_by, "Added to", instance.project.name
                )
        if old_instance and (
            old_instance.work_product_privilege != instance.work_product_privilege
            or old_instance.confidential_privilege != instance.confidential_privilege
            or old_instance.attorney_client_privilege != instance.attorney_client_privilege
        ):
            privilege_log_history.delay(instance, "workflow")
        if old_instance:
            if old_instance and (
                old_instance.owner != instance.owner
                or old_instance.assigned_to_users.all() != instance.assigned_to_users.all()
                or instance.assigned_to_group.all() != old_instance.assigned_to_group.all()
                or old_instance.status != instance.status
            ):
                workflow_change_user(instance)


def pre_save_attachment(sender, instance, *args, **kwargs):
    if instance.content_type:
        if instance.content_type.model == "project":
            instance.project = Project.objects.get(pk=instance.object_id)
        if instance.content_type.model == "workflow":
            instance.workflow = Workflow.objects.get(pk=instance.object_id)
        if instance.content_type.model == "task":
            instance.task = Task.objects.get(pk=instance.object_id)


def assigned_to_group_changed_project(sender, **kwargs):
    action = kwargs.get('action')
    project = kwargs.get('instance')
    if action == 'post_add':
        project.is_assignee_changed = True
        for group_id in kwargs.get('pk_set'):
            projects_group = WorkGroup.objects.get(pk=group_id)
            [
                project_assigned_notification(project, group_member)
                for group_member in projects_group.group_members.all()
            ]

    if action == 'post_remove':
        project.is_assignee_changed = True
        for group_id in kwargs.get('pk_set'):
            projects_group = WorkGroup.objects.get(pk=group_id)
            [
                project_removed_notification(project, group_member)
                for group_member in projects_group.group_members.all()
            ]


def assigned_to_group_changed_workflow(sender, **kwargs):
    action = kwargs.get('action')
    workflow = kwargs.get('instance')
    if action == 'post_add':
        workflow.is_assignee_changed = True
        for group_id in kwargs.get('pk_set'):
            workflows_group = WorkGroup.objects.get(pk=group_id)
            [
                workflow_assigned_notification(workflow, group_member)
                for group_member in workflows_group.group_members.all()
            ]
    if action == 'post_remove':
        workflow.is_assignee_changed = True
        for group_id in kwargs.get('pk_set'):
            workflows_group = WorkGroup.objects.get(pk=group_id)
            [
                workflow_removed_notification(workflow, group_member)
                for group_member in workflows_group.group_members.all()
            ]


def assigned_to_group_changed_task(sender, **kwargs):
    action = kwargs.get('action')
    task = kwargs.get('instance')
    if action == 'post_add':
        task.is_assignee_changed = True
        for group_id in kwargs.get('pk_set'):
            tasks_group = WorkGroup.objects.get(pk=group_id)
            [
                task_assigned_to_group_notification(task, tasks_group, group_member)
                for group_member in tasks_group.group_members.all()
            ]
    if action == 'post_remove':
        task.is_assignee_changed = True


def workgroup_add_member(sender, instance, created, *args, **kwargs):
    if created:
        workgroup_add_user(instance)


def workgroup_remove_member(sender, instance, *args, **kwargs):
    workgroup_remove_user(instance)


pre_save.connect(project_due_date_change, sender=Project)
pre_save.connect(workflow_due_date_change, sender=Workflow)
pre_save.connect(task_pre_save, sender=Task)
post_save.connect(create_task_notification, sender=Task)
m2m_changed.connect(assigned_to_users_workflow, sender=Workflow.assigned_to_users.through)
m2m_changed.connect(assigned_to_users_changed, sender=Project.assigned_to_users.through)
pre_save.connect(pre_save_attachment, sender=Attachment)
m2m_changed.connect(assigned_to_group_changed_project, sender=Project.assigned_to_group.through)
m2m_changed.connect(assigned_to_group_changed_workflow, sender=Workflow.assigned_to_group.through)
m2m_changed.connect(assigned_to_group_changed_task, sender=Task.assigned_to_group.through)
post_save.connect(workgroup_add_member, sender=WorkGroupMember)
pre_delete.connect(workgroup_remove_member, sender=WorkGroupMember)


def _create_tasks_base_on_workflow(task_fixtures, user, workflow):
    from projects.api.serializers import (
        TaskCreateSerializer,
        TaskFixtureDetailSerializer,
    )
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    request = Request(APIRequestFactory().get(''))
    request.user = user
    """
    {"fixture_id": "task_id"}
    """
    mapper_fixture_task = {}
    with transaction.atomic():
        while task_fixtures:
            task_fixture = task_fixtures.pop(0)
            if task_fixture.prior_task_id and task_fixture.prior_task_id not in mapper_fixture_task:
                task_fixtures.append(task_fixture)
                continue
            if task_fixture.after_task_id and task_fixture.after_task_id not in mapper_fixture_task:
                task_fixtures.append(task_fixture)
                continue

            data = TaskFixtureDetailSerializer(task_fixture, context={'request': request}).data
            if not task_fixture.assigned_to and not task_fixture.assigned_to_group.exists():
                data['assigned_to'] = workflow.created_by.id
            if task_fixture.due_date:
                data['due_date'] = now() + timedelta(days=task_fixture.due_date)
            if task_fixture.start_date:
                data['start_date'] = now() + timedelta(days=task_fixture.start_date)
            data['workflow'] = workflow.id
            data['after_task'] = mapper_fixture_task.get(data.pop('after_task', None), None)
            data['prior_task'] = mapper_fixture_task.get(data.pop('prior_task', None), None)
            # Attachment and tags
            data['task_tags'] = list(map(lambda x: x.get('tag', None), data.pop('task_tags', [])))
            attachments = data.pop('attachments', [])
            data['attachments'] = [
                Attachment.objects.duplicate_instance(attachment.get('id', None)).pk for attachment in attachments
            ]
            serializer = TaskCreateSerializer(data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            mapper_fixture_task[task_fixture.id] = serializer.instance.pk


def workflow_create_tasks_base_on_template(sender, instance, created, *args, **kwargs):
    if created and instance.template:
        task_fixtures = list(instance.template.task_fixtures.all())
        _create_tasks_base_on_workflow(task_fixtures, instance.created_by, instance)


post_save.connect(workflow_create_tasks_base_on_template, sender=Workflow)


def project_create_workflows_base_on_template(sender, instance, created, *args, **kwargs):
    if created and instance.template:
        from projects.api.serializers import (
            WorkflowCreateSerializer,
            WorkflowFixtureDetailSerializer,
        )
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        request = Request(APIRequestFactory().get(''))

        request.user = instance.created_by
        fixtures = list(instance.template.workflow_fixtures.all())
        """
        {"fixture_id": "task_id"}
        """
        mapper_fixture_task = {}
        with transaction.atomic():
            while fixtures:
                fixture = fixtures.pop(0)
                data = WorkflowFixtureDetailSerializer(fixture, context={'request': request}).data
                if not fixture.assigned_to_users.exists() and not fixture.assigned_to_group.exists():
                    data['assigned_to_users'] = [instance.created_by.id]
                if not fixture.owner:
                    data['owner'] = instance.created_by.id
                if fixture.due_date:
                    data['due_date'] = now() + timedelta(days=fixture.due_date)
                if fixture.start_date:
                    data['start_date'] = now() + timedelta(days=fixture.start_date)
                data['project'] = instance.id
                # Attachment and tags
                data['workflow_tags'] = list(map(lambda x: x.get('tag', None), data.pop('workflow_tags', [])))
                attachments = data.pop('attachments', [])
                data['attachments'] = [
                    Attachment.objects.duplicate_instance(attachment.get('id', None)).pk for attachment in attachments
                ]
                serializer = WorkflowCreateSerializer(data=data, context={'request': request})
                serializer.is_valid(raise_exception=True)
                serializer.save()
                mapper_fixture_task[fixture.id] = serializer.instance.pk
                task_fixtures = list(fixture.task_fixtures.all())
                _create_tasks_base_on_workflow(task_fixtures, instance.created_by, serializer.instance)


post_save.connect(project_create_workflows_base_on_template, sender=Project)
