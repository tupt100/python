from authentication.models import GroupAndPermission
from rest_framework import permissions

from customers.models import Feature, FeatureName

permission_map = {
    'importance': 'change-importance',
    'attachments': 'upload-docs',
    'due_date': 'change-due-date',
    'assigned_to': 'reassign-task',
    'status': ['reopen-task', 'mark-as-completed',
               'status-update'],
    'workflow': 'associate-to-workflow',
    'owner': 'assign-owner',
    'project': 'associate-to-project',
    'assigned_to_users': 'add-team-members',

}


class CustomPermission(permissions.BasePermission):
    """
    When you use this Permission add model attribute
    """
    message = "You don't have permission to perform this action"

    def has_permission(self, request, view):
        if not request.user.id:
            return False
        group = request.user.group
        company = request.user.company
        model = view.model
        if not all([group, company, model]):
            return False
        model_name = permission_category = model._meta.model_name
        method_name = view.action
        # print('permission_category, method_name: ', permission_category,
        #       method_name)
        if method_name in ['list', 'retrieve', 'create']:
            # For list, details and create
            slug = self.get_slug_by_method(permission_category, method_name)
            # print('slug: ', slug)
            if slug in \
                    [permission_category + "_" +
                     permission_category + '-create']:
                group_permission = GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category=permission_category,
                    permission__slug=slug,
                    has_permission=True).exists()
                if group_permission:
                    if self.has_privilege_keys(request):
                        # check if the group has create/edit
                        #  privileges permission
                        privilege_slug = permission_category + "_" + \
                                         "create-edit-privilege-selector"
                        category = permission_category
                        privilege_permission = \
                            GroupAndPermission.objects.filter(
                                group=group, company=company,
                                permission__permission_category=category,
                                permission__slug=privilege_slug,
                                has_permission=True).exists()
                        return privilege_permission
                    return True

            if method_name in ['list', 'retrieve']:
                # manage view-all permission
                slug_mine = permission_category + "_" + \
                            permission_category + '-view'
                slug_all = \
                    permission_category + "_" + \
                    permission_category + '-view-all'
                group_permission = GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category=permission_category,
                    permission__slug=slug_mine,
                    has_permission=True
                ).exists() or GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category=permission_category,
                    permission__slug=slug_all,
                    has_permission=True).exists()
                if not group_permission:
                    return False
                else:
                    return True
        elif method_name == 'partial_update':
            slug = permission_category + "_" + permission_category + '-update'
            group_permission = GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=permission_category,
                permission__slug=slug, has_permission=True).exists()
            if group_permission:
                #     If user have update permission
                if request.data:
                    all_permissions = list(GroupAndPermission.objects.filter(
                        group=group,
                        company=company,
                        permission__permission_category=permission_category,
                        has_permission=True
                    ).values_list('permission__slug', flat=True))
                    # print('all_permissions: ', all_permissions)
                    app_slug = permission_category + "_"
                    app_slug_delete = permission_category + "_"
                    change_value_count = len(request.data)
                    change_permission_count = 0
                    for data_key, data_value in request.data.items():
                        if data_key in ['project_tags', 'workflow_tags',
                                        'task_tags', 'document_tags',
                                        'description', 'is_private',
                                        'completed_percentage', 'start_date',
                                        'prior_task', 'after_task', 'custom_fields_value']:
                            change_permission_count += 1
                            continue
                        # check if name exists in the request data
                        if data_key == 'name':
                            change_permission_count += 1
                            continue
                        if data_key == 'status':
                            if model_name == 'task':
                                if data_value in ['2', 2, 5, '5', 6, '6',
                                                  7, '7', 8, '8', 9, '9',
                                                  10, '10', 11, '11',
                                                  12, '12', 13, '13',
                                                  14, '14', 15, '15',
                                                  16, '16', 17, '17',
                                                  18, '18', 19, '19',
                                                  20, '20', 21, '21',
                                                  22, '22', 23, '23',
                                                  24, '24', 25, '25',
                                                  26, '26', 27, '27',
                                                  28, '28', 29, '29',
                                                  30, '30', 31, '31',
                                                  32, '32', 33, '33',
                                                  34, '34']:
                                    change_permission_count += 1
                                    continue
                                if data_value in ['1', 1] and app_slug + \
                                        'reopen-task' in all_permissions:
                                    change_permission_count += 1
                                    continue
                                if data_value in ['3', 3] and app_slug + \
                                        'mark-as-completed' in all_permissions:
                                    change_permission_count += 1
                                    continue
                                if data_value in ['4', 4] and \
                                        app_slug_delete + \
                                        model_name + '-delete' in \
                                        all_permissions:
                                    change_permission_count += 1
                                    continue
                            else:
                                if data_value in ['4', 4, 5, '5']:
                                    change_permission_count += 1
                                    continue
                                if data_value in ['2', 2] and app_slug + \
                                        'mark-as-completed' in all_permissions:
                                    change_permission_count += 1
                                    continue
                                if data_value in ['3', 3] and \
                                        app_slug_delete + \
                                        model_name + '-delete' in \
                                        all_permissions:
                                    change_permission_count += 1
                                    continue
                        # increase change count per privileges present in data
                        if data_key == 'attorney_client_privilege':
                            if model_name + "_" + \
                                    "create-edit-privilege-selector" in \
                                    all_permissions:
                                change_permission_count += 1
                                continue
                        if data_key == 'work_product_privilege':
                            if model_name + "_" + \
                                    "create-edit-privilege-selector" in \
                                    all_permissions:
                                change_permission_count += 1
                                continue
                        if data_key == 'confidential_privilege':
                            if model_name + "_" + \
                                    "create-edit-privilege-selector" in \
                                    all_permissions:
                                change_permission_count += 1
                                continue
                        if data_key == 'assigned_to_group':
                            change_permission_count += 1
                            continue
                        else:
                            permission_attr = permission_map.get(data_key)
                            if permission_attr and \
                                    type(permission_attr) == str:
                                if app_slug + permission_attr in \
                                        all_permissions:
                                    change_permission_count += 1
                                    continue
                        # self.message = "You don't have permission
                        #                 to update {}".format(data_key)
                    # print(change_value_count, change_permission_count)
                    if change_permission_count == change_value_count:
                        return True
                else:
                    return True

        elif method_name == 'swap_rank':
            slug = permission_category + "_" + "set-rank-drag-drop"
            group_permission = GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=permission_category,
                permission__slug=slug, has_permission=True).exists()
            # print('group_permission: ', group_permission)
            if group_permission:
                # If user have update permission
                return True

        # check if the group has permission to rename title.
        elif method_name == 'rename_title':
            slug = slug = permission_category + "_" + permission_category + \
                          '-edit-name'
            group_permission = GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=permission_category,
                permission__slug=slug, has_permission=True).exists()
            if group_permission:
                return True
        elif method_name in ['request_associate_to_task',
                             'project_add_messages',
                             'workflow_add_messages',
                             'task_add_messages',
                             'task_delete_messages',
                             'workflow_details_statistic',
                             'workflow_delete_messages',
                             'task_details_statistic',
                             'project_delete_messages',
                             'workflow_project_statistic']:
            return True
        return False

    @staticmethod
    def get_slug_by_method(permission_category, method_name):
        slug = permission_category + "_" + permission_category
        if method_name in ['list', 'retrieve']:
            slug += '-view'
        elif method_name == 'create':
            slug += '-create'
        return slug

    @staticmethod
    def has_privilege_keys(request):
        # check if any of the privilege keys are present in request data
        return ('work_product_privilege' in request.data.keys() or
                'attorney_client_privilege' in request.data.keys() or
                'confidential_privilege' in request.data.keys())


class RankPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.method in ['HEAD', 'OPTIONS']:
            return True

        if view.action in ['partial_update']:
            if request.user.is_authenticated:
                group = request.user.group
                company = request.user.company
                if not all([group, company]):
                    return False
                model = view.model._meta.model_name
                slug = model + "_" + "set-rank-drag-drop"
                group_permission = GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category=model,
                    permission__slug=slug,
                    has_permission=True).exists()
                if group_permission:
                    # If user have update permission
                    return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class WorkGoupPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['partial_update',
                           'workgroup_add_members',
                           'workgroup_remove_members',
                           'list', 'retrieve', 'destroy']:
            return True
        else:
            return False


class WorkGroupMemberPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['workgroup_create']:
            return True
        else:
            return False


class CompanyWorkGroupPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['list']:
            return True
        else:
            return False


class ServiceDeskAttachmentPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.user.is_anonymous and view.action == "create":
            return True
        else:
            return False


class ServiceDeskPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.user.is_anonymous and view.action == "create":
            return True
        else:
            return False


class RequestPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user
        group = user.group
        company = user.company
        if view.action in ['list', 'retrieve',
                           'destroy', 'bulk_task_creation',
                           'create_new_request',
                           'task_request_create']:
            if GroupAndPermission.objects.filter(
                    group=group,
                    company=company,
                    permission__permission_category='request',
                    permission__slug='request_request-view',
                    has_permission=True).exists():
                return True
            return False
        else:
            return False


class PendingRequestPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action == 'list' and request.user.is_anonymous:
            return True
        return False


class SubmittedRequestPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['list', 'retrieve',
                           'add_document_to_request',
                           'submitrequest_messages',
                           'submitrequest_add_messages',
                           'submitrequest_delete_messages'] \
                and request.user.is_anonymous:
            return True
        return False


class UserWorkGroupPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action == "list":
            return True
        else:
            return False


class AttachmentPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['create', 'list',
                           'retrieve', 'partial_update',
                           'rename', 'destroy']:
            for method in ['POST', 'GET', 'PUT', 'PATCH', 'data']:
                if 'external_url' in getattr(request, method, {}):
                    if not Feature.objects.active().filter(
                        key=FeatureName.EXTERNAL_DOCS,
                        value=True
                    ).exists():
                        return False

            return True
        else:
            return False


class TagPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['create', 'list']:
            return True
        elif view.action in ['partial_update',
                             'destroy', 'retrieve']:
            if request.user.is_owner or \
                    request.user.group.is_company_admin:
                return True
            else:
                return False
        else:
            return False


class UserWorkGroupPermissionCustom(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "workgroup_details_statistic",
                           "retrieve"]:
            return True
        else:
            return False


class GroupWorkLoadReportPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "group_workload_file_generate"]:
            return True
        else:
            return False


class TagReportPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "tag_report_file_generate"]:
            return True
        else:
            return False


class TeamMemberWorkLoadPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list",
                           "team_member_workload_file_generate"]:
            return True
        else:
            return False


class WorkProductivityLogPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "productivity_file_generate",
                           "productivity_graph_generate"]:
            return True
        else:
            return False


class EfficiencyPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "efficiency_file_generate"]:
            return True
        else:
            return False
