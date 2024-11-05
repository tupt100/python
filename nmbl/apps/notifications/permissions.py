from rest_framework import permissions


class MyNotificationPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action in ['read_all_notifications', 'list',
                           'partial_update', 'destroy']:
            return True
        else:
            return False


class CompanyUserNotificationPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if view.action == 'list':
            return True
        else:
            return False
