# Create your tasks here
from __future__ import absolute_import, unicode_literals

from authentication.adapters import get_invitations_adapter
from celery import shared_task
from django.apps import apps
from django.db.models import Q
from projects.models import (TaskRank, WorkflowRank, ProjectRank, Task,
                             Workflow, Project)

from .models import Group, GroupAndPermission, Organization


@shared_task
def send_celery_email(email_template, user_email, context,
                      title, from_email):
    get_invitations_adapter().send_mail(
        email_template, user_email, context,
        title, from_email)


def create_customize_groups():
    orgs = Organization.objects.all()
    for org_obj in orgs:
        # create 5 groups
        group_create_data_objs = [{
            "name": "Business Manager",
            "organization": org_obj.id,
            "status": "active"
        }, {
            "name": "Legal Team",
            "organization": org_obj.id,
            "status": "active"
        }, {
            "name": "Legal Dept Assistant",
            "organization": org_obj.id,
            "status": "active"
        }, {
            "name": "General Counsel",
            "organization": org_obj.id,
            "status": "active"
        }, {
            "name": "Admin",
            "organization": org_obj.id,
            "status": "active"
        }]
        for group_create_data_obj in group_create_data_objs:
            Group.objects.create(**group_create_data_obj)
            # create 42 permission objects in DefaultPermission


def user_rank(user, company):
    group = user.group
    # get User related task and create rank
    if GroupAndPermission.objects.filter(
            group=user.group, company=user.company,
            permission__permission_category='task',
            has_permission=True,
            permission__slug='task_task-view-all').exists():
        q_obj = Q()
        q_obj.add(Q(is_private=True, organization=company) &
                  Q(Q(assigned_to=user) |
                    Q(created_by=user) |
                    Q(assigned_to_group__group_members=user)), Q.OR)
        q_obj.add(Q(is_private=False, organization=company), Q.OR)
        task_queryset = Task.objects.filter(q_obj).distinct()
        if not GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category='task',
                permission__slug='task_view-archived',
                has_permission=True).exists():
            task_queryset = task_queryset.exclude(status__in=[3, 4])
        for completed_task in task_queryset.filter(status__in=[3, 4]):
            TaskRank.objects.create(user=user, task=completed_task, rank=0)
        for task in task_queryset.exclude(status__in=[3, 4]):
            user_task_last_rank = TaskRank.objects.filter(
                user=user, is_active=True).order_by('-rank').first()
            if not user_task_last_rank:
                TaskRank.objects.create(user=user, task=task, rank=1)
            else:
                TaskRank.objects.create(user=user, task=task,
                                        rank=int(user_task_last_rank.rank) + 1)
    # get user related project and create rank
    if GroupAndPermission.objects.filter(
            group=user.group, company=user.company,
            permission__permission_category='project',
            has_permission=True,
            permission__slug='project_project-view-all').exists():
        project_queryset = Project.objects.filter(
            organization=company)
        if not GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category='project',
                permission__slug='project_view-archived',
                has_permission=True).exists():
            project_queryset = project_queryset.exclude(status__in=[2, 3])
        for project in project_queryset:
            user_project_last_rank = ProjectRank.objects.filter(
                user=user, is_active=True
            ).order_by('-rank').first()
            if not user_project_last_rank:
                ProjectRank.objects.create(user=user,
                                           project=project, rank=1)
            else:
                ProjectRank.objects.create(
                    user=user, project=project,
                    rank=int(user_project_last_rank.rank) + 1)
    # get user related workflow and create rank
    if GroupAndPermission.objects.filter(
            group=user.group, company=user.company,
            permission__permission_category='workflow',
            has_permission=True,
            permission__slug='workflow_workflow-view-all').exists():
        workflow_queryset = Workflow.objects.filter(
            organization=company)
        if not GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category='workflow',
                permission__slug='workflow_view-archived',
                has_permission=True).exists():
            workflow_queryset = workflow_queryset.exclude(status__in=[2, 3])
        for workflow in workflow_queryset:
            user_workflow_last_rank = WorkflowRank.objects.filter(
                user=user, is_active=True).order_by('-rank').first()
            if not user_workflow_last_rank:
                WorkflowRank.objects.create(
                    user=user, workflow=workflow, rank=1)
            else:
                WorkflowRank.objects.create(
                    user=user, workflow=workflow,
                    rank=int(user_workflow_last_rank.rank) + 1)


def user_rank_update(user):
    group = user.group
    company = user.company
    models = ['project', 'task', 'workflow']
    model_rank_dict = {'project': 'ProjectRank',
                       'workflow': 'WorkflowRank',
                       'task': 'TaskRank'}
    for model in models:
        view_all_slug = model + '_' + model + '-view-all'
        view_mine_slug = model + '_' + model + '-view'
        if GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=model,
                permission__slug=view_all_slug,
                has_permission=True
        ).exists():
            pass
        elif GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=model,
                permission__slug=view_mine_slug,
                has_permission=True
        ).exists():
            pass
        else:
            rank_model_str = model_rank_dict.get(model)
            rank_model = apps.get_model('projects', rank_model_str)
            rank_model.objects.delete(user=user)
