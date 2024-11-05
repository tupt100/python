from django.shortcuts import get_object_or_404
from rest_framework.permissions import SAFE_METHODS
from rest_framework import permissions
from authentication.models import GroupAndPermission
from customers.features.models import FeatureName, Feature
from ..models import WorkflowTemplate, ProjectTemplate


class BaseTemplatePermission(permissions.BasePermission):
    """
    Base class for check permission base on group and permission level
    """

    def get_group(self, request, view):
        group = request.user.group
        return group

    def get_company(self, request, view):
        return request.user.company

    def get_model(self, request, view):
        return view.model

    def check_required_value(self, request, view):
        if request.user.is_anonymous:
            return False

        group = self.get_group(request=request, view=view)
        company = self.get_company(request, view)
        model = self.get_model(request, view)
        return all([group, company, model])

    def check_group_permission(self, request, view, feature_name):
        if not Feature.objects.active().filter(
                key=feature_name,
                value=True
        ).exists():
            return False
        if not self.check_required_value(request, view):
            return False
        model = self.get_model(request, view)
        group = self.get_group(request, view)
        company = self.get_company(request, view)

        permission_category = model._meta.model_name
        method_name = view.action
        slug = self.get_slug_by_method(permission_category, method_name)
        group_permission = GroupAndPermission.objects.filter(
            group=group,
            company=company,
            permission__permission_category=permission_category,
            permission__slug=slug,
            has_permission=True
        ).exists()
        return group_permission

    @staticmethod
    def get_slug_by_method(permission_category, method_name):
        slug = method_name
        if method_name in ['list', 'retrieve']:
            slug = 'view'
        slug = f'{permission_category}_{permission_category}-{slug}'
        return slug


class WorkflowTemplateCreatePermission(BaseTemplatePermission):
    """
    A class from which control for create action.
    """

    def has_permission(self, request, view):
        return self.check_group_permission(request, view, FeatureName.WORKFLOW_TEMPLATE)


class WorkflowTemplateViewPermission(BaseTemplatePermission):
    """
    A class from which control for view.
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.WORKFLOW_TEMPLATE)

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.WORKFLOW_TEMPLATE)


class WorkflowTemplateUpdatePermission(BaseTemplatePermission):
    """
    A class from which control for update.
    """

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.WORKFLOW_TEMPLATE)


class WorkflowTemplateDestroyPermission(BaseTemplatePermission):
    """
    A class from which control for destroy.
    """

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.WORKFLOW_TEMPLATE)


class CustomFieldWorkflowTemplateOwner(permissions.BasePermission):
    """
    A class from which control the owner of task or not.
    """

    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return True
        if request.method in SAFE_METHODS:
            return True
        for method in ['POST', 'GET', 'data']:
            object_id = getattr(request, method, {}).get('object_id', None)
            if object_id:
                workflow_template = get_object_or_404(WorkflowTemplate.objects.active(), pk=object_id)
                return workflow_template.created_by == request.user
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """

        return obj.content_object.created_by == request.user


class ProjectTemplateCreatePermission(BaseTemplatePermission):
    """
    A class from which control for create action.
    """

    def has_permission(self, request, view):
        return self.check_group_permission(request, view, FeatureName.PROJECT_TEMPLATE)


class ProjectTemplateViewPermission(BaseTemplatePermission):
    """
    A class from which control for view.
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.PROJECT_TEMPLATE)

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.PROJECT_TEMPLATE)


class ProjectTemplateUpdatePermission(BaseTemplatePermission):
    """
    A class from which control for update.
    """

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.PROJECT_TEMPLATE)


class ProjectTemplateDestroyPermission(BaseTemplatePermission):
    """
    A class from which control for destroy.
    """

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.check_group_permission(request, view, FeatureName.PROJECT_TEMPLATE)


class CustomFieldProjectTemplateOwner(permissions.BasePermission):
    """
    A class from which control the owner of task or not.
    """

    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return True
        if request.method in SAFE_METHODS:
            return True
        for method in ['POST', 'GET', 'data']:
            object_id = getattr(request, method, {}).get('object_id', None)
            if object_id:
                project_template = get_object_or_404(ProjectTemplate.objects.active(), pk=object_id)
                return project_template.created_by == request.user
        return False

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return obj.content_object.created_by == request.user
