# Create your tasks here
from __future__ import absolute_import, unicode_literals

import datetime

from authentication.models import GroupAndPermission
from authentication.models import User
from celery import shared_task
from customers.models import Client
from django.db.models import F, Q
from django_tenants.utils import schema_context

from .helpers import project_due_date_notification, \
    workflow_due_date_notification, \
    task_due_date_notification, \
    task_due_date_to_group_notification, handle_webhook_task_inbound
from .models import Project, Task, Workflow, \
    ServiceDeskUserInformation
from .models import TaskRank, WorkflowRank, ProjectRank, \
    ServiceDeskAttachment


# celery -A nmbl beat -l info
# celery -A nmbl worker -l info


@shared_task
def project_due_date_check():
    with schema_context('public'):
        all_tenants_list = list(
            Client.objects.values_list('schema_name', flat=True))
        for tenant_sc in all_tenants_list:
            project_due_date_check_tenant_specific.delay(tenant_sc)


@shared_task
def project_due_date_check_tenant_specific(tenant_sc_name):
    with schema_context(tenant_sc_name):
        today = datetime.datetime.now()
        yesterday = today + datetime.timedelta(days=-1)
        for project in Project.objects.filter(
                due_date__date__lt=today.date(),
                is_email_notified=False,
                status__in=[1, 4, 5]):
            for assigned_user in project.assigned_to_users.all():
                project_due_date_notification(project, assigned_user)
            for project_group in project.assigned_to_group.all():
                [project_due_date_notification(project, group_member)
                 for group_member in project_group.group_members.all()]
            project_due_date_notification(project, project.owner)
            project.is_email_notified = True
            project.save()

        for workflow in Workflow.objects.filter(
                due_date__date__lt=today.date(),
                is_email_notified=False,
                status__in=[1, 4, 5]):
            for assigned_user in workflow.assigned_to_users.all():
                workflow_due_date_notification(workflow, assigned_user)
            for workflow_group in workflow.assigned_to_group.all():
                [workflow_due_date_notification(workflow, group_member)
                 for group_member in workflow_group.group_members.all()]
            workflow_due_date_notification(workflow, workflow.owner)
            workflow.is_email_notified = True
            workflow.save()

        for task in Task.objects.filter(
                due_date__date__lt=today.date(),
                is_email_notified=False,
        ).exclude(status__in=[3, 4]):
            for task_group in task.assigned_to_group.all():
                [task_due_date_to_group_notification(task, group_member)
                 for group_member in task_group.group_members.all()]
            task_due_date_notification(task)
            task.is_email_notified = True
            task.save()
        # to check that access_token is expire or not
        for service_desk in \
                ServiceDeskUserInformation.objects.filter(
                    expiration_date__date=today):
            service_desk.is_expire = True
            service_desk.save()
        # to delete unnecessary documents from
        # service desk which is not converted in request
        for attachments in ServiceDeskAttachment.objects.filter(
                created_at__date__lte=yesterday,
                can_remove=True):
            attachments.delete()

    return ''


def rerankTask(self, validated_data):
    request = self.context.get('request')
    task_obj = self.instance
    old_rank = task_obj.rank
    new_rank = validated_data.get('rank')
    if new_rank < old_rank:
        TaskRank.objects.filter(
            user=request.user,
            rank__gte=new_rank,
            rank__lt=old_rank).exclude(
            rank=0).update(rank=F('rank') + 1)
        # 1(new- small value) -> 3(old- large value)
        # for i in range(old_rank, new_rank, 1):
        #     TaskRank.objects.filter(
        #     user=request.user, rank=i + 1,
        #     is_active=True).update(rank=i)
    elif new_rank > old_rank:
        TaskRank.objects.filter(
            user=request.user,
            rank__lte=new_rank,
            rank__gt=old_rank).exclude(
            rank=0).update(rank=F('rank') - 1)
        # 3(old- large value) -> 1(new- small value)
        # for i in reversed(range(new_rank, old_rank, 1)):
        #     TaskRank.objects.filter(user=request.user,
        #     rank=i, is_active=True).update(rank=i + 1)


def rerankWorkflow(self):
    request = self.context.get('request')
    workflow_obj = self.instance
    old_rank = workflow_obj.rank
    new_rank = request.data.get('rank')
    if new_rank < old_rank:
        WorkflowRank.objects.filter(
            user=request.user,
            rank__gte=new_rank,
            rank__lt=old_rank).update(rank=F('rank') + 1)
        # 1(new- small value) -> 3(old- large value)
        # for i in range(old_rank, new_rank, 1):
        #     WorkflowRank.objects.filter(
        #     user=request.user, rank=i + 1,
        #     is_active=True).update(rank=i)
    elif new_rank > old_rank:
        WorkflowRank.objects.filter(
            user=request.user,
            rank__lte=new_rank,
            rank__gt=old_rank).update(rank=F('rank') - 1)
        # 3(old- large value) -> 1(new- small value)
        # for i in reversed(range(new_rank,
        #   old_rank, 1)):
        #     WorkflowRank.objects.filter(user=request.user,
        #     rank=i, is_active=True).update(rank=i + 1)


def rerankProject(self):
    request = self.context.get('request')
    project_obj = self.instance
    old_rank = project_obj.rank
    new_rank = request.data.get('rank')
    if new_rank < old_rank:
        ProjectRank.objects.filter(
            user=request.user,
            rank__gte=new_rank,
            rank__lt=old_rank).update(rank=F('rank') + 1)
        # 1(new- small value) -> 3(old- large value)
        # for i in range(old_rank, new_rank, 1):
        #     ProjectRank.objects.filter(user=request.user,
        #     rank=i + 1, is_active=True).update(rank=i)
    elif new_rank > old_rank:
        ProjectRank.objects.filter(
            user=request.user,
            rank__lte=new_rank,
            rank__gt=old_rank).update(rank=F('rank') - 1)
        # 3(old- large value) -> 1(new- small value)
        # for i in reversed(range(new_rank, old_rank, 1)):
        #     ProjectRank.objects.filter(user=request.user,
        #     rank=i, is_active=True).update(rank=i + 1)


def create_workflowrank(instance):
    workflow = instance
    company = workflow.organization
    # make list of workflow related user(
    # created, assign to and assign
    # group user, and workflow view all permission user)
    related_users = []
    # get user query who have workflow view all permission
    view_all_permission_user = User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='workflow_workflow-view-all'
    )
    related_users.extend(view_all_permission_user)
    # get user query who have view permission
    view_permission_user = User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='workflow_workflow-view')
    # add workflow created user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if (instance.created_by not in related_users and
            instance.created_by in view_permission_user):
        related_users.append(instance.created_by)
    # add workflow owner user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if instance.owner and (instance.owner not in related_users and
                           instance.owner in view_permission_user):
        related_users.append(instance.owner)
    # add workflow assign user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    for assign_user in instance.assigned_to_users.all():
        if (assign_user not in related_users and
                assign_user in view_permission_user):
            related_users.append(assign_user)
    # Append workflow group's members to the users list
    # condition : check user not exist on related_users &
    #             need permission task view
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member not in related_users and
                    group_member in view_permission_user):
                related_users.append(group_member)
    # create workflow rank for task related user
    for user in related_users:
        user_workflow_last_rank = WorkflowRank.objects.filter(
            user=user, is_active=True).order_by('-rank').first()
        if not user_workflow_last_rank:
            WorkflowRank.objects.create(
                user=user, workflow=workflow, rank=1)
        else:
            WorkflowRank.objects.create(
                user=user, workflow=workflow,
                rank=int(user_workflow_last_rank.rank) + 1)
    return instance


def create_projectrank(instance):
    project = instance
    company = project.organization
    # make list of project related user
    #   (created, assign to and assign group user,
    # and project view all permission user)
    related_users = []
    # get user query who have project view all permission
    view_all_permission_user = User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='project_project-view-all')
    related_users.extend(view_all_permission_user)
    # get user query who have view permission
    view_permission_user = User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='project_project-view')
    # add project created user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if (instance.created_by not in related_users and
            instance.created_by in view_permission_user):
        related_users.append(instance.created_by)
    # add project owner user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if instance.owner and (instance.owner not in related_users and
                           instance.owner in view_permission_user):
        related_users.append(instance.owner)
    # add project assign user on related_user list
    # condition : check user not exist on
    #             related_users & need permission task view
    for assign_user in instance.assigned_to_users.all():
        if (assign_user not in related_users and
                assign_user in view_permission_user):
            related_users.append(assign_user)
    # Append project group's members to the users list
    # condition : check user not exist on related_users &
    #             need permission task view
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member not in related_users and
                    group_member in view_permission_user):
                related_users.append(group_member)
    # create task rank for task related user
    for user in related_users:
        user_project_last_rank = ProjectRank.objects.filter(
            user=user, is_active=True).order_by('-rank').first()
        if not user_project_last_rank:
            ProjectRank.objects.create(
                user=user, project=project, rank=1)
        else:
            ProjectRank.objects.create(
                user=user, project=project,
                rank=int(user_project_last_rank.rank) + 1)
    return instance


def create_taskrank(instance):
    task = instance
    company = task.organization
    # get user query who have view permission
    view_permission_user = list(User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='task_task-view'))
    # get user query who have task view all permission
    if not task.is_private:
        related_users = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view-all'))
    else:
        related_users = []
        view_permission_user += list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view-all')
        )
    # add task created user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if (instance.created_by not in related_users and
            instance.created_by in view_permission_user):
        related_users.append(instance.created_by)
    # add task assign user on related_user list
    # condition : check user not exist on related_users &
    #              need permission task view
    if (instance.assigned_to and (
            instance.assigned_to not in related_users and
            instance.assigned_to in view_permission_user)):
        related_users.append(instance.assigned_to)
    # Append task group's members to the users list
    #     # if they are not in view-all list
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member not in related_users and
                    group_member in view_permission_user):
                related_users.append(group_member)
    # create task rank for task related user
    for user in related_users:
        user_task_last_rank = TaskRank.objects.filter(
            user=user, is_active=True
        ).order_by('-rank').first()
        if not user_task_last_rank:
            TaskRank.objects.create(
                user=user, task=task, rank=1)
        else:
            TaskRank.objects.create(
                user=user, task=task,
                rank=int(user_task_last_rank.rank) + 1)
    return instance


def project_change_user(instance):
    project = instance
    company = project.organization
    # get user query who have project view all permission
    related_users = list(User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='project_project-view-all'
    ).values_list('id', flat=True).distinct())
    # get user query who have view permission
    view_permission_user = list(User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='project_project-view'
    ).values_list('id', flat=True).distinct())
    if project.status in [2, 3]:
        archived_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='project_view-archived'
        ).values_list('id', flat=True).distinct())
        related_users = [x for x in related_users if x in archived_user]
        view_permission_user = [
            x for x in view_permission_user if x in archived_user]
    # add project created user on related_user list
    # condition : check user not exist on related_users &
    #             need permission project view
    if (instance.created_by.id not in related_users and
            instance.created_by.id in view_permission_user):
        related_users.append(instance.created_by.id)
    # add project owner user on related_user list
    # condition : check user not exist on related_users &
    #             need permission project view
    if instance.owner and (instance.owner.id not in related_users and
                           instance.owner.id in view_permission_user):
        related_users.append(instance.owner.id)
    # add project assign user on related_user list
    # condition : check user not exist on related_users &
    #             need permission project view
    for assign_user in instance.assigned_to_users.all():
        if (assign_user.id not in related_users and
                assign_user.id in view_permission_user):
            related_users.append(assign_user.id)
    # Append project group's members to the users list
    # condition : check user not exist on related_users &
    #             need permission project view
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member.id not in related_users and
                    group_member.id in view_permission_user):
                related_users.append(group_member.id)
    # get list of user already have project rank
    existing_project_rank_user = list(ProjectRank.objects.filter(
        project=project).values_list('user__id', flat=True).distinct())
    # get new assigned user list
    # [x for x in related_users
    # if x not in existing_task_rank_user]
    new_assigned_user = User.objects.filter(
        id__in=related_users).exclude(
        id__in=existing_project_rank_user)
    # getlist of user removed from task
    # removed_user = [x for x in existing_task_rank_user
    # if x not in related_users]
    removed_user = User.objects.filter(
        id__in=existing_project_rank_user).exclude(
        id__in=related_users)
    # create project rank for task related user
    for user in new_assigned_user:
        user_project_last_rank = ProjectRank.objects.filter(
            user=user, is_active=True
        ).order_by('-rank').first()
        if not user_project_last_rank:
            ProjectRank.objects.create(
                user=user, project=project, rank=1)
        else:
            ProjectRank.objects.create(
                user=user, project=project,
                rank=int(user_project_last_rank.rank) + 1)
    # remove project rank user which don't
    # have permission and re-rank it
    for user in removed_user:
        ProjectRank.objects.filter(
            user=user, project=project).delete()
        for index, active_proojectrank in enumerate(
                ProjectRank.objects.filter(user=user).order_by('rank')):
            active_proojectrank.rank = index + 1
            active_proojectrank.is_active = True
            active_proojectrank.save()


def workflow_change_user(instance):
    workflow = instance
    company = workflow.organization
    # get user query who have task view all permission
    related_users = list(User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='workflow_workflow-view-all'
    ).values_list('id', flat=True).distinct())
    # get user query who have view permission
    view_permission_user = list(User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='workflow_workflow-view'
    ).values_list('id', flat=True).distinct())
    if workflow.status in [2, 3]:
        archived_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='workflow_view-archived'
        ).values_list('id', flat=True).distinct())
        related_users = [x for x in related_users
                         if x in archived_user]
        view_permission_user = [
            x for x in view_permission_user if x in archived_user]
    # add workflow created user on related_user list
    # condition : check user not exist on related_users
    #             & need permission workflow view
    if (instance.created_by.id not in related_users and
            instance.created_by.id in view_permission_user):
        related_users.append(instance.created_by.id)
    # add workflow owner user on related_user list
    # condition : check user not exist on related_users
    #             & need permission workflow view
    if instance.owner and (instance.owner.id not in related_users and
                           instance.owner.id in view_permission_user):
        related_users.append(instance.owner.id)
    # add workflow assign user on related_user list
    # condition : check user not exist on related_users
    #             & need permission workflow view
    for assign_user in instance.assigned_to_users.all():
        if (assign_user.id not in related_users and
                assign_user.id in view_permission_user):
            related_users.append(assign_user.id)
    # Append task group's members to the users list
    #     # if they are not in view-all list
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member.id not in related_users and
                    group_member.id in view_permission_user):
                related_users.append(group_member.id)
    # get list of user already have workflow rank
    existing_workflow_rank_user = list(WorkflowRank.objects.filter(
        workflow=workflow).values_list(
        'user__id', flat=True).distinct())
    # get new assigned user list
    # [x for x in related_users
    # if x not in existing_workflow_rank_user]
    new_assigned_user = User.objects.filter(
        id__in=related_users).exclude(
        id__in=existing_workflow_rank_user)
    # getlist of user removed from workflow
    # removed_user = [x for x in existing_workflow_rank_user
    # if x not in related_users]
    removed_user = User.objects.filter(
        id__in=existing_workflow_rank_user).exclude(
        id__in=related_users)
    # create task rank for task related user
    for user in new_assigned_user:
        user_workflow_last_rank = WorkflowRank.objects.filter(
            user=user, is_active=True
        ).order_by('-rank').first()
        if not user_workflow_last_rank:
            WorkflowRank.objects.create(
                user=user, workflow=workflow, rank=1)
        else:
            WorkflowRank.objects.create(
                user=user, workflow=workflow,
                rank=int(user_workflow_last_rank.rank) + 1)
    # remove task rank user which dont have permission and rerank it
    for user in removed_user:
        WorkflowRank.objects.filter(
            user=user, workflow=workflow).delete()
        for index, active_workflowrank in enumerate(
                WorkflowRank.objects.filter(user=user).order_by('rank')):
            active_workflowrank.rank = index + 1
            active_workflowrank.is_active = True
            active_workflowrank.save()


def task_change_user(instance):
    task = instance
    company = task.organization
    old_task_instance = Task.objects.get(id=instance.id)
    if task.status not in [3, 4] and old_task_instance.status in [3, 4]:
        TaskRank.objects.filter(task=instance).delete()
    # get user query who have task view all permission
    if not task.is_private:
        # get user query who have view permission
        view_permission_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view'
        ).values_list('id', flat=True).distinct())
        related_users = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view-all'
        ).values_list('id', flat=True).distinct())
    else:
        related_users = []
        permission_list = ['task_task-view-all', 'task_task-view']
        view_permission_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug__in=permission_list
        ).values_list('id', flat=True).distinct())
    if task.status in [3, 4]:
        archived_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_view-archived'
        ).values_list('id', flat=True).distinct())
        related_users = list(User.objects.filter(
            Q(id__in=related_users) & Q(id__in=archived_user)
        ).values_list('id', flat=True).distinct())
        # related_users = [x for x in related_users
        #                  if x in archived_user]
        view_permission_user = list(User.objects.filter(
            Q(id__in=view_permission_user)
            & Q(id__in=archived_user)).values_list(
            'id', flat=True).distinct())
        # view_permission_user = [x for x in view_permission_user
        #                         if x in archived_user]
    # add task created user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if (instance.created_by.id not in related_users and
            instance.created_by.id in view_permission_user):
        related_users.append(instance.created_by.id)
    # add task assign user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if instance.assigned_to:
        if (instance.assigned_to.id not in related_users and
                instance.assigned_to.id in view_permission_user):
            related_users.append(instance.assigned_to.id)
    # Append task group's members to the users list
    #     # if they are not in view-all list
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member.id not in related_users and
                    group_member.id in view_permission_user):
                related_users.append(group_member.id)
    # get list of user already have task rank
    existing_task_rank_user = list(TaskRank.objects.filter(
        task=task).values_list(
        'user__id', flat=True).distinct())
    # get new assigned user list
    # [x for x in related_users
    # if x not in existing_task_rank_user]
    new_assigned_user = User.objects.filter(
        id__in=related_users).exclude(
        id__in=existing_task_rank_user)
    # getlist of user removed from task
    # removed_user = [x for x in existing_task_rank_user
    #                 if x not in related_users]
    removed_user = User.objects.filter(
        id__in=existing_task_rank_user).exclude(
        id__in=related_users)
    # remove task rank user which don't have permission and rerank it
    for user in removed_user:
        user_remove_task = TaskRank.objects.filter(
            user=user, task=task).first()
        if user_remove_task and user_remove_task.rank != 0:
            TaskRank.objects.filter(
                user=user, rank__gt=user_remove_task.rank
            ).exclude(rank=0).update(rank=F('rank') - 1)
        user_remove_task.delete()
        # for index, active_taskrank in enumerate(
        #         TaskRank.objects.filter(user=user
        #         ).exclude(rank=0).order_by('rank')):
        #     active_taskrank.rank = index + 1
        #     active_taskrank.is_active = True
        #     active_taskrank.save()
    if task.status in [3, 4]:
        users = TaskRank.objects.filter(
            task=instance).values_list('user_id', flat=True)
        for user in users:
            user_completed_task = TaskRank.objects.filter(
                task=instance, user_id=user).first()
            if user_completed_task and user_completed_task.rank != 0:
                TaskRank.objects.filter(
                    user__id=user,
                    rank__gt=user_completed_task.rank).exclude(
                    rank=0).update(rank=F('rank') - 1)
        TaskRank.objects.filter(task=instance).update(rank=0)
        for user in new_assigned_user:
            TaskRank.objects.create(user=user, task=task, rank=0)
    else:
        # create task rank for task related user
        for user in new_assigned_user:
            user_task_last_rank = TaskRank.objects.filter(
                user=user).exclude(rank=0).order_by('-rank').first()
            if not user_task_last_rank:
                TaskRank.objects.create(user=user, task=task, rank=1)
            else:
                TaskRank.objects.create(
                    user=user, task=task,
                    rank=int(user_task_last_rank.rank) + 1)


def permission_group_update(instance):
    group = instance
    organization = group.organization
    instance_user = User.objects.filter(
        group=group, company=organization)
    for user in instance_user:
        group = user.group
        company = user.company
        # Task rank update start
        """
        variable
        u_p_t_l > user permitted task list
        u_e_t_r > user existing task rank
        n_t_a_u > new task assigned to user
        r_t_a > list of task which removed access for user

        """
        if GroupAndPermission.objects.filter(
                group=user.group,
                company=user.company,
                has_permission=True,
                permission__slug='task_task-view-all').exists():
            q_obj = Q()
            q_obj.add(Q(is_private=True, organization=company) &
                      Q(Q(assigned_to=user) |
                        Q(created_by=user) |
                        Q(assigned_to_group__group_members=user)), Q.OR)
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = Task.objects.filter(
                q_obj).values_list('id', flat=True).distinct()
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='task',
                    permission__slug='task_view-archived',
                    has_permission=True).exists():
                queryset = queryset.exclude(status__in=[3, 4])
            u_p_t_l = list(queryset)
        elif GroupAndPermission.objects.filter(
                group=user.group,
                company=user.company,
                has_permission=True,
                permission__slug='task_task-view').exists():
            queryset = Task.objects.filter(
                Q(organization=user.company),
                Q(assigned_to=user) |
                Q(created_by=user) |
                Q(assigned_to_group__group_members=user)
            ).values_list('id', flat=True).distinct()
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='task',
                    permission__slug='task_view-archived',
                    has_permission=True).exists():
                queryset = queryset.exclude(status__in=[3, 4])
            u_p_t_l = list(queryset)
        else:
            u_p_t_l = []
        # get list of existing task rank
        u_e_t_r = list(TaskRank.objects.filter(
            user=user).values_list(
            'task__id', flat=True).distinct())
        # get removed task from user
        removed_task = Task.objects.filter(
            id__in=u_e_t_r).exclude(
            id__in=u_p_t_l)
        r_t_a = list(removed_task.values_list('id', flat=True).distinct())
        # r_t_a = [x for x in u_e_t_r if x not in u_p_t_l]
        TaskRank.objects.filter(
            user=user, task__id__in=r_t_a).delete()
        for index, active_taskrank in enumerate(
                TaskRank.objects.filter(user=user).exclude(
                    task__status__in=[3, 4]).order_by('rank')):
            active_taskrank.rank = index + 1
            active_taskrank.is_active = True
            active_taskrank.save()
        # get new task where user have permission
        new_assign_task = Task.objects.filter(
            id__in=u_p_t_l).exclude(
            id__in=u_e_t_r)
        for completed_task in new_assign_task.filter(status__in=[3, 4]):
            TaskRank.objects.create(
                user=user, task=completed_task, rank=0)
        # n_t_a_u = [x for x in u_p_t_l if x not in u_e_t_r]
        for task in new_assign_task.exclude(status__in=[3, 4]):
            user_task_last_rank = TaskRank.objects.filter(
                user=user, is_active=True).order_by('-rank').first()
            if not user_task_last_rank:
                TaskRank.objects.create(
                    user=user, task=task, rank=1)
            else:
                TaskRank.objects.create(
                    user=user, task=task,
                    rank=int(user_task_last_rank.rank) + 1)
        # Task rank update end

        # project rank update start
        if GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='project',
                has_permission=True,
                permission__slug='project_project-view-all').exists():
            project_queryset = Project.objects.filter(
                organization=company)
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='project',
                    permission__slug='project_view-archived',
                    has_permission=True).exists():
                project_queryset = project_queryset.exclude(status__in=[2, 3])
            project_queryset_ids = list(
                project_queryset.values_list('id', flat=True).distinct())
        elif GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='project',
                has_permission=True,
                permission__slug='project_project-view').exists():
            project_queryset = Project.objects.filter(
                Q(organization=company),
                Q(owner=user) |
                Q(assigned_to_users=user) |
                Q(created_by=user) |
                Q(assigned_to_group__group_members=user))
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='project',
                    permission__slug='project_view-archived',
                    has_permission=True).exists():
                project_queryset = project_queryset.exclude(status__in=[2, 3])
            project_queryset_ids = list(
                project_queryset.values_list('id', flat=True).distinct())
        else:
            project_queryset_ids = []
        # get list of existing project rank
        existing_project_rank_id = list(ProjectRank.objects.filter(
            user=user).values_list(
            'project__id', flat=True).distinct())
        # get removed project from user
        removed_project_rank = Project.objects.filter(
            id__in=existing_project_rank_id).exclude(
            id__in=project_queryset_ids)
        removed_project_rank_id = list(
            removed_project_rank.values_list('id', flat=True).distinct())
        ProjectRank.objects.filter(
            user=user, project__id__in=removed_project_rank_id
        ).delete()
        for index, active_projectrank in enumerate(
                ProjectRank.objects.filter(user=user).order_by('rank')):
            active_projectrank.rank = index + 1
            active_projectrank.is_active = True
            active_projectrank.save()
        # get new project where user have permission
        new_assign_project = Project.objects.filter(
            id__in=project_queryset_ids).exclude(
            id__in=existing_project_rank_id)
        for project in new_assign_project:
            user_project_last_rank = ProjectRank.objects.filter(
                user=user, is_active=True
            ).order_by('-rank').first()
            if not user_project_last_rank:
                ProjectRank.objects.create(
                    user=user, project=project, rank=1)
            else:
                ProjectRank.objects.create(
                    user=user, project=project,
                    rank=int(user_project_last_rank.rank) + 1)
        # project rank update end

        # workflow rank update start
        if GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                has_permission=True,
                permission__slug='workflow_workflow-view-all'
        ).exists():
            workflow_queryset = Workflow.objects.filter(
                organization=company)
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='workflow',
                    permission__slug='workflow_view-archived',
                    has_permission=True).exists():
                workflow_queryset = workflow_queryset.exclude(
                    status__in=[2, 3])
            workflow_queryset_ids = list(
                workflow_queryset.values_list(
                    "id", flat=True).distinct())
        elif GroupAndPermission.objects.filter(
                group=group,
                company=company,
                permission__permission_category='workflow',
                has_permission=True,
                permission__slug='workflow_workflow-view').exists():
            workflow_queryset = Workflow.objects.filter(
                Q(organization=company),
                Q(owner=user) |
                Q(assigned_to_users=user) |
                Q(created_by=user) |
                Q(assigned_to_group__group_members=user))
            if not GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='workflow',
                    permission__slug='workflow_view-archived',
                    has_permission=True).exists():
                workflow_queryset = workflow_queryset.exclude(
                    status__in=[2, 3])
            workflow_queryset_ids = list(
                workflow_queryset.values_list(
                    "id", flat=True).distinct())
        else:
            workflow_queryset_ids = []
        # get list of existing workflow rank
        existing_workflow_rank_id = list(WorkflowRank.objects.filter(
            user=user).values_list(
            'workflow__id', flat=True).distinct())
        # get removed workflow from user
        removed_workflow_rank = Workflow.objects.filter(
            id__in=existing_workflow_rank_id).exclude(
            id__in=workflow_queryset_ids)
        removed_workflow_rank_id = list(
            removed_workflow_rank.values_list('id', flat=True).distinct())
        WorkflowRank.objects.filter(
            user=user,
            workflow__id__in=removed_workflow_rank_id
        ).delete()
        for index, active_workflowrank in enumerate(
                WorkflowRank.objects.filter(user=user).order_by('rank')):
            active_workflowrank.rank = index + 1
            active_workflowrank.is_active = True
            active_workflowrank.save()
        # get new workflow where user have permission
        new_assign_workflow = Workflow.objects.filter(
            id__in=workflow_queryset_ids).exclude(
            id__in=existing_workflow_rank_id)
        for workflow in new_assign_workflow:
            user_workflow_last_rank = WorkflowRank.objects.filter(
                user=user, is_active=True).order_by('-rank').first()
            if not user_workflow_last_rank:
                WorkflowRank.objects.create(
                    user=user, workflow=workflow, rank=1)
            else:
                WorkflowRank.objects.create(
                    user=user, workflow=workflow,
                    rank=int(user_workflow_last_rank.rank) + 1)


def workgroup_add_user(instance):
    user = instance.group_member
    workgroup = instance.work_group
    # task rank create
    # get task id which is related to this workgroup
    # and get task id which have already rank
    task_instance = Task.objects.filter(
        assigned_to_group=workgroup).values_list(
        'id', flat=True).distinct()
    existing_rank = TaskRank.objects.filter(
        user=user).values_list(
        'task__id', flat=True).distinct()
    # remove those task which have rank
    new_task = Task.objects.filter(
        id__in=task_instance).exclude(id__in=existing_rank)
    # create task rank
    for completed_task in new_task.filter(status__in=[3, 4]):
        TaskRank.objects.create(user=user, task=completed_task, rank=0)
    for task in new_task.exclude(status__in=[3, 4]):
        user_task_last_rank = TaskRank.objects.filter(
            user=user, is_active=True).order_by('-rank').first()
        if not user_task_last_rank:
            TaskRank.objects.create(user=user, task=task, rank=1)
        else:
            TaskRank.objects.create(
                user=user, task=task,
                rank=int(user_task_last_rank.rank) + 1)
    # project rank create
    # get project which is related to this workgroup
    # and get project which have already rank
    project_instance = Project.objects.filter(
        assigned_to_group=workgroup).values_list(
        'id', flat=True).distinct()
    existing_rank = ProjectRank.objects.filter(
        user=user).values_list(
        'project__id', flat=True).distinct()
    # remove those project which have rank
    new_project = Project.objects.filter(
        id__in=project_instance).exclude(id__in=existing_rank)
    # create project rank
    for project in new_project:
        user_project_last_rank = ProjectRank.objects.filter(
            user=user, is_active=True).order_by('-rank').first()
        if not user_project_last_rank:
            ProjectRank.objects.create(
                user=user, project=project, rank=1)
        else:
            ProjectRank.objects.create(
                user=user, project=project,
                rank=int(user_project_last_rank.rank) + 1)
    # workflow rank create
    # get workflow which is related to this workgroup
    # and get workflow which have already rank
    workflow_instance = Workflow.objects.filter(
        assigned_to_group=workgroup
    ).values_list('id', flat=True).distinct()
    existing_rank = WorkflowRank.objects.filter(
        user=user).values_list(
        'workflow__id', flat=True).distinct()
    # remove those workflow which have rank
    new_workflow = Workflow.objects.filter(
        id__in=workflow_instance).exclude(id__in=existing_rank)
    # create workflow rank
    for workflow in new_workflow:
        user_workflow_last_rank = WorkflowRank.objects.filter(
            user=user, is_active=True).order_by('-rank').first()
        if not user_workflow_last_rank:
            WorkflowRank.objects.create(
                user=user, workflow=workflow, rank=1)
        else:
            WorkflowRank.objects.create(
                user=user, workflow=workflow,
                rank=int(user_workflow_last_rank.rank) + 1)


def workgroup_remove_user(instance):
    user = instance.group_member
    workgroup = instance.work_group
    # remove task rank
    # get task which have this work group and
    #  not direct assign with this user
    task_instance = Task.objects.filter(
        assigned_to_group=workgroup).exclude(
        Q(assigned_to=user) | Q(created_by=user)
    ).values_list('id', flat=True).distinct()
    TaskRank.objects.filter(user=user,
                            task__id__in=task_instance).delete()
    # re-rank of available task
    for index, active_taskrank in enumerate(
            TaskRank.objects.filter(user=user).exclude(
                task__status__in=[3, 4]).order_by('rank')):
        active_taskrank.rank = index + 1
        active_taskrank.is_active = True
        active_taskrank.save()
    # remove project rank
    # get project which have this workgroup and
    #   not direct assign with this user
    project_instance = Project.objects.filter(
        assigned_to_group=workgroup).exclude(
        Q(assigned_to_users=user) | Q(created_by=user) |
        Q(created_by=user)).values_list('id', flat=True).distinct()
    ProjectRank.objects.filter(
        user=user, project__id__in=project_instance).delete()
    # re-rank of available project
    for index, active_projectrank in enumerate(
            ProjectRank.objects.filter(user=user).order_by('rank')):
        active_projectrank.rank = index + 1
        active_projectrank.is_active = True
        active_projectrank.save()
    # remove workflow rank
    # get workflow which have this workgroup and
    #   not direct assign with this user
    workflow_instance = Workflow.objects.filter(
        assigned_to_group=workgroup).exclude(
        Q(assigned_to_users=user) | Q(created_by=user) |
        Q(created_by=user)
    ).values_list('id', flat=True).distinct()
    WorkflowRank.objects.filter(
        user=user,
        workflow__id__in=workflow_instance).delete()
    # rerank of available task
    for index, active_workflowrank in enumerate(
            WorkflowRank.objects.filter(
                user=user).order_by('rank')):
        active_workflowrank.rank = index + 1
        active_workflowrank.is_active = True
        active_workflowrank.save()


def task_rerank_alluser(instance):
    task = instance
    company = task.organization
    # get user query who have task view all permission
    if not task.is_private:
        # get user query who have view permission
        view_permission_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view'
        ).values_list('id', flat=True).distinct())
        related_users = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_task-view-all'
        ).values_list('id', flat=True).distinct())
    else:
        related_users = []
        permission_list = ['task_task-view-all', 'task_task-view']
        view_permission_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug__in=permission_list
        ).values_list('id', flat=True).distinct())
    if task.status in [3, 4]:
        archived_user = list(User.objects.filter(
            company=company,
            group__group_permission__has_permission=True,
            group__group_permission__company=company,
            group__group_permission__permission__slug='task_view-archived'
        ).values_list('id', flat=True).distinct())
        related_users = list(User.objects.filter(
            Q(id__in=related_users) & Q(id__in=archived_user)
        ).values_list('id', flat=True).distinct())
        # related_users = [x for x in related_users if x in archived_user]
        view_permission_user = list(User.objects.filter(
            Q(id__in=view_permission_user)
            & Q(id__in=archived_user)).values_list(
            'id', flat=True).distinct())
        # view_permission_user = [x for x in view_permission_user
        #                           if x in archived_user]
    # add task created user on related_user list
    # condition : check user not exist on
    #             related_users & need permission task view
    if (instance.created_by.id not in related_users and
            instance.created_by.id in view_permission_user):
        related_users.append(instance.created_by.id)
    # add task assign user on related_user list
    # condition : check user not exist on related_users &
    #             need permission task view
    if instance.assigned_to:
        if (instance.assigned_to.id not in related_users and
                instance.assigned_to.id in view_permission_user):
            related_users.append(instance.assigned_to.id)
    # Append task group's members to the users list
    #     # if they are not in view-all list
    for group in instance.assigned_to_group.all():
        for group_member in group.group_members.all():
            if (group_member.id not in related_users and
                    group_member.id in view_permission_user):
                related_users.append(group_member.id)
    # get list of user already have task rank
    existing_task_rank_user = list(TaskRank.objects.filter(
        task=task).values_list('user__id', flat=True).distinct())
    # get new assigned user list
    new_assigned_user = User.objects.filter(
        id__in=related_users).exclude(
        id__in=existing_task_rank_user)
    # getlist of user removed from task
    # removed_user = [x for x in existing_task_rank_user
    #                 if x not in related_users]
    removed_user = User.objects.filter(
        id__in=existing_task_rank_user).exclude(
        id__in=related_users)
    # remove task rank user which don't
    # have permission and re-rank it
    for user in removed_user:
        TaskRank.objects.filter(
            user=user, task=task).delete()
        for index, active_taskrank in enumerate(
                TaskRank.objects.filter(
                    user=user).exclude(rank=0).order_by('rank')):
            active_taskrank.rank = index + 1
            active_taskrank.is_active = True
            active_taskrank.save()
    if task.status in [3, 4]:
        users = TaskRank.objects.filter(
            task=instance).values_list('user_id', flat=True)
        for user in users:
            TaskRank.objects.filter(user__id=user,
                                    task=task).update(rank=0)
            for index, active_taskrank in enumerate(
                    TaskRank.objects.filter(
                        user__id=user
                    ).exclude(rank=0).order_by('rank')):
                active_taskrank.rank = index + 1
                active_taskrank.is_active = True
                active_taskrank.save()
        for user in new_assigned_user:
            TaskRank.objects.create(user=user, task=task, rank=0)
    else:
        # create task rank for task related user
        for user in new_assigned_user:
            user_task_last_rank = TaskRank.objects.filter(
                user=user).exclude(rank=0).order_by('-rank').first()
            if not user_task_last_rank:
                TaskRank.objects.create(
                    user=user, task=task, rank=1)
            else:
                TaskRank.objects.create(
                    user=user, task=task,
                    rank=int(user_task_last_rank.rank) + 1)


@shared_task
def test_webhook_task_inbound():
    import os
    fixture_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../fixtures'))
    fixture_file_path = os.path.join(fixture_dir, 'test_webhook_task_inbound.json')
    if os.path.exists(fixture_file_path):
        with open(fixture_file_path, 'r') as f:
            data_str = f.read()
            handle_webhook_task_inbound(data_str)
