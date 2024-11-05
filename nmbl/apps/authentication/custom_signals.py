import uuid

from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from projects.models import (TaskRank, WorkflowRank,
                             ProjectRank, Task,
                             Workflow, Project)
from rest_framework.authtoken.models import Token

from .adapters import get_invitations_adapter
from .models import (Organization, Invitation, Group,
                     User, GroupAndPermission, CompanyInformation)
from .tasks import user_rank


@receiver(post_save, sender=Organization)
def organisation_handler(sender, instance, created, **kwargs):
    if created:
        try:
            # Create default permission on organisation create
            organization = instance
            for group in Group.objects.all():
                for default_permission in group.default_permission_group.all():
                    GroupAndPermission.objects.create(
                        group=group,
                        company=organization,
                        permission=default_permission.permission,
                        has_permission=default_permission.has_permission,
                    )
        except Exception as e:
            print(str(e))
        if instance.name:
            data = {'company': instance,
                    'message': "whether you are a client or "
                               "a member of {}, you can create "
                               "requests for legal team "
                               "through the service desk "
                               "portal.\n\nyou'll be emailed "
                               "notifications of all updates "
                               "on your task.".format(instance.name)}
            CompanyInformation.objects.get_or_create(**data)
        email = instance.owner_email.lower().strip()
        owner_name = instance.owner_name
        company_name = instance.name
        try:
            group = Group.objects.get(name="General Counsel")
            invited_by_group = group.id
        except Exception as e:
            print(e)
            grp = Group.objects.create(name="General Counsel")
            invited_by_group = grp.id
        invited = Invitation.objects.create(
            email=email, invited_by_company=instance,
            invited_by_group_id=invited_by_group,
            key=str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex)),
            is_owner=True)
        if invited:
            send_invitation(email, owner_name, company_name, invited_by_group,
                            invited)


def send_invitation(email, owner_name, company_name, group, invited):
    from django.db import connection
    site = "You have been granted early access to Proxy!"
    subject = "You have been granted early access to Proxy!"
    base_url = settings.SITE_URL.format(
        connection.schema_name).replace(':8080', '')
    invite_url = base_url + "/auth/signup/" + str(invited.key)
    context = {"email": email, "name": owner_name, "site_name": site,
               'company': company_name, 'invite_url': invite_url,
               'sender_name': owner_name,
               'site_url': settings.SITE_URL.format(connection.schema_name)}
    email_template = 'invitations/email/organization_email_invite'
    from_email = '{} <{}>'.format("PROXY SYSTEM", settings.DEFAULT_FROM_EMAIL)
    get_invitations_adapter().send_mail(
        email_template, email, context, subject, from_email)
    invited.sent = timezone.now()
    invited.save()


@receiver(post_save, sender=User)
def user_handler(sender, instance, created, update_fields=None, **kwargs):
    if created:
        try:
            user = instance
            # Create User token
            Token.objects.get_or_create(user=user)
            company = user.company
            if company:
                user_rank(user, company)
        except Exception as e:
            print(str(e))


@receiver(pre_save, sender=User)
def user_rank_update(sender, instance, update_fields=None, **kwargs):
    # check if user group(Role) has been updated. And if updated,
    # create/delete rank objects of components accordingly.
    if instance.id:
        instance_old_user_group = User.objects.get(id=instance.id).group
    else:
        instance_old_user_group = None
    if instance.id and (instance_old_user_group != instance.group):
        user = instance
        group = instance.group
        company = user.company
        # Task rank update start
        """
        variable
        u_p_t_l > user permited task list
        u_e_t_r > user existing task rank
        n_t_a_u > new task assigned to user
        r_t_a > list of task which removed access for user
        """
        if GroupAndPermission.objects.filter(
                group=user.group, company=user.company,
                has_permission=True,
                permission__slug='task_task-view-all').exists():
            q_obj = Q()
            q_obj.add(Q(is_private=True, organization=company) &
                      Q(Q(assigned_to=user) |
                        Q(created_by=user) |
                        Q(assigned_to_group__group_members=user)), Q.OR)
            q_obj.add(Q(is_private=False, organization=company), Q.OR)
            queryset = Task.objects.filter(q_obj).values_list(
                'id', flat=True).distinct()
            if not GroupAndPermission.objects.filter(
                    group=group, company=company,
                    permission__permission_category='task',
                    permission__slug='task_view-archived',
                    has_permission=True).exists():
                queryset = queryset.exclude(status__in=[3, 4])
            u_p_t_l = list(queryset)
        elif GroupAndPermission.objects.filter(
                group=user.group, company=user.company,
                has_permission=True,
                permission__slug='task_task-view').exists():
            queryset = Task.objects.filter(
                Q(organization=user.company),
                Q(assigned_to=user) |
                Q(created_by=user) |
                Q(assigned_to_group__group_members=user)).values_list(
                'id', flat=True).distinct()
            if not GroupAndPermission.objects.filter(
                    group=group, company=company,
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
        TaskRank.objects.filter(user=user, task__id__in=r_t_a).delete()
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
            TaskRank.objects.create(user=user,
                                    task=completed_task, rank=0)
        # n_t_a_u = [x for x in u_p_t_l if x not in u_e_t_r]
        for task in new_assign_task.exclude(status__in=[3, 4]):
            user_task_last_rank = TaskRank.objects.filter(
                user=user, is_active=True).order_by('-rank').first()
            if not user_task_last_rank:
                TaskRank.objects.create(user=user, task=task, rank=1)
            else:
                TaskRank.objects.create(user=user, task=task,
                                        rank=int(user_task_last_rank.rank) + 1)
        # Task rank update end

        # project rank update start
        if GroupAndPermission.objects.filter(
                group=group, company=company,
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
            project_queryset_ids = list(
                project_queryset.values_list('id', flat=True).distinct())
        elif GroupAndPermission.objects.filter(
                group=group, company=company,
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
                    group=group, company=company,
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
            user=user, project__id__in=removed_project_rank_id).delete()
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
                user=user, is_active=True).order_by('-rank').first()
            if not user_project_last_rank:
                ProjectRank.objects.create(user=user, project=project, rank=1)
            else:
                ProjectRank.objects.create(
                    user=user, project=project,
                    rank=int(user_project_last_rank.rank) + 1)
        # project rank update end

        # workflow rank update start
        if GroupAndPermission.objects.filter(
                group=group, company=company,
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
                workflow_queryset = workflow_queryset.exclude(
                    status__in=[2, 3])
            workflow_queryset_ids = list(
                workflow_queryset.values_list("id", flat=True).distinct())
        elif GroupAndPermission.objects.filter(
                group=group, company=company,
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
                    group=group, company=company,
                    permission__permission_category='workflow',
                    permission__slug='workflow_view-archived',
                    has_permission=True).exists():
                workflow_queryset = workflow_queryset.exclude(
                    status__in=[2, 3])
            workflow_queryset_ids = list(
                workflow_queryset.values_list("id", flat=True).distinct())
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
            removed_workflow_rank.values_list(
                'id', flat=True).distinct())
        WorkflowRank.objects.filter(
            user=user,
            workflow__id__in=removed_workflow_rank_id).delete()
        for index, active_workflowrank in enumerate(
                WorkflowRank.objects.filter(
                    user=user).order_by('rank')):
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
                    user=user,
                    workflow=workflow,
                    rank=int(user_workflow_last_rank.rank) + 1)
        # workflow rank update end
