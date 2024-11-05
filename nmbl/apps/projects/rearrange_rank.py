from authentication.models import User
from django.db.models import Max

from .models import TaskRank, WorkflowRank, ProjectRank


def rearrange_task_rank(task):
    all_task_rank = TaskRank.objects.filter(task=task)
    users = all_task_rank.values_list('user', flat=True)[::1]
    related_users = []
    related_users.extend(User.objects.filter(
        pk__in=users, is_delete=False))
    for user in related_users:
        # set incremental rank for active task
        for index, active_taskrank in enumerate(
                TaskRank.objects.filter(
                    user=user).exclude(
                    task__status__in=[3, 4]).order_by('rank')):
            active_taskrank.rank = index + 1
            active_taskrank.is_active = True
            active_taskrank.save()
        # removing rank from in-active task
        for index, inactive_taskrank in enumerate(
                all_task_rank.filter(user_id=user).exclude(
                    task__status__in=[3, 4]).order_by('rank')):
            inactive_taskrank.rank = index + 1
            inactive_taskrank.is_active = False
            inactive_taskrank.save()


def reactivate_task_rank(task):
    # list of TaskRank objects for the Task
    task_rank_objects = list(TaskRank.objects.filter(task=task))
    company = task.organization
    # Users in the company with view-all permissions
    users = User.objects.filter(
        company=company,
        group__group_permission__has_permission=True,
        group__group_permission__company=company,
        group__group_permission__permission__slug='task_task-view-all')
    for task_rank_object in task_rank_objects:
        # for existing TaskRank users with view-all permissions when Task is
        # re-activated create activate the TaskRank object with new rank.
        if task_rank_object.user in users:
            max_user_active_rank = TaskRank.objects.filter(
                user=task_rank_object.user, is_active=True) \
                .aggregate(Max('rank'))['rank__max']
            if not max_user_active_rank:
                max_user_active_rank = 0
            task_rank_object.rank = max_user_active_rank + 1
            task_rank_object.is_active = True
            task_rank_object.save()
        else:
            # Else if the user is view-mine permission user delete
            # the TaskRank
            # object for the user.
            task_rank_object.delete()
    # if Task has been assigned to a user with a view-mine
    # permission create
    # a new TaskRank object for the user.
    if task.assigned_to not in User.objects.filter(taskrank__task=task):
        max_user_active_rank = TaskRank.objects.filter(
            user=task.assigned_to, is_active=True) \
            .aggregate(Max('rank'))['rank__max']
        if not max_user_active_rank:
            max_user_active_rank = 0
        TaskRank.objects.create(user=task.assigned_to,
                                task=task,
                                rank=(max_user_active_rank + 1),
                                is_active=True)


def rearrange_workflow_rank(workflow):
    all_workflow_rank = WorkflowRank.objects.filter(workflow=workflow)
    users = all_workflow_rank.values_list('user', flat=True)[::1]
    related_users = []
    related_users.extend(User.objects.filter(pk__in=users, is_delete=False))
    for user in related_users:
        # set incremental rank for active workflow
        for index, active_workflowrank in enumerate(
                WorkflowRank.objects.filter(
                    user=user, workflow__status__in=[1, 4, 5]
                ).order_by('rank')):
            active_workflowrank.rank = index + 1
            active_workflowrank.is_active = True
            active_workflowrank.save()
        # removing rank from in-active workflow
        for index, inactive_workflowrank in enumerate(
                all_workflow_rank.filter(user_id=user).exclude(
                    workflow__status__in=[1, 4, 5]).order_by('rank')):
            inactive_workflowrank.rank = index + 1
            inactive_workflowrank.is_active = False
            inactive_workflowrank.save()


def rearrange_project_rank(project):
    all_project_rank = ProjectRank.objects.filter(project=project)
    users = all_project_rank.values_list('user', flat=True)[::1]
    related_users = []
    related_users.extend(User.objects.filter(
        pk__in=users, is_delete=False))
    all_project_rank.delete()
    for user in related_users:
        # set incremental rank for active project
        for index, active_projectrank in enumerate(
                ProjectRank.objects.filter(
                    user=user, project__status__in=[1, 4, 5]
                ).order_by('rank')):
            active_projectrank.rank = index + 1
            active_projectrank.is_active = True
            active_projectrank.save()
        # removing rank from in-active project
        for index, inactive_projectrank in enumerate(
                all_project_rank.filter(user_id=user).exclude(
                    project__status__in=[1, 4, 5]).order_by('rank')):
            inactive_projectrank.rank = index + 1
            inactive_projectrank.is_active = False
            inactive_projectrank.save()
