from rest_framework import permissions


class PermissionManagerPermission(permissions.BasePermission):
    message = "You don't have permission to perform this action"

    def has_permission(self, request, view):
        try:
            if request.user.is_authenticated:
                if request.user.is_owner or \
                        request.user.group.is_company_admin:
                    return True
        except Exception as e:
            print("exception:", e)
            return False
        return False


class BulkInvitePermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action == 'send_bulk_invitation':
            return True
        else:
            return False


class CompanyInformationPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action == 'list':
            return True
        else:
            return False


class CompanyUserPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "destroy",
                           "partial_update", "retrieve"]:
            return True
        else:
            return False


class UserPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["partial_update", "change_password",
                           "me", "upload_avatar"]:
            return True
        else:
            return False


class GroupListPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "retrieve"]:
            return True
        else:
            return False


class ListPendingInvitationPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ["list", "destroy",
                           "partial_update"]:
            return True
        else:
            return False
