import django_filters
from authentication.models import User
from django.db.models import Q
from django_filters import rest_framework as filters

from .models import (Attachment, TaskRank, WorkflowRank, ProjectRank, Task,
                     AuditHistory, Tag, WorkGroup, ServiceDeskExternalRequest,
                     Privilage_Change_Log, TagChangeLog, GroupWorkLoadLog,
                     TeamMemberWorkLoadLog, WorkProductivityLog)


class MultiChoiceFilter(filters.Filter):
    """
    Filter class for multiple values separated by comma
    """

    def filter(self, qs, value):
        if not value:
            return qs

        values = [int(x) for x in value.split(',') if x.strip().isdigit()]
        lookup = self.field_name + '__in'
        qs = qs.filter(**{lookup: values}).distinct()
        return qs


class MultiChoiceTagFilter(filters.Filter):
    """
    Filter class for multiple values separated by comma
    """

    def filter(self, qs, value):
        if not value:
            return qs
        values = [int(x) for x in value.split(',') if x.strip().isdigit()]
        for value in values:
            q = Q(**{"%s" % self.field_name: value})
            qs = qs.filter(q)
        return qs


FILTER_CHOICES = (
    (16, 'project'),
    (19, 'task'),
)

MODEL_CHOICES = (
    ("project", "Project"),
    ("workflow", "Workflow"),
    ("task", "Task"),
    ("attachment", "Attachment"),
)


class AttachmentFilterSet(filters.FilterSet):
    type = filters.ChoiceFilter(field_name="content_type", lookup_expr='exact',
                                choices=FILTER_CHOICES)
    project = MultiChoiceFilter(field_name="project", lookup_expr='exact')
    workflow = MultiChoiceFilter(field_name="workflow", lookup_expr='exact')
    task = MultiChoiceFilter(field_name="task", lookup_expr='exact')
    tag = MultiChoiceFilter(field_name='document_tags__id')
    created_at = django_filters.DateFromToRangeFilter(field_name='created_at')
    created_by = MultiChoiceFilter(field_name="created_by")

    class Meta:
        model = Attachment
        fields = ['type']


class TaskFilterSet(filters.FilterSet):
    created_at = django_filters.DateFromToRangeFilter(
        field_name='task__created_at')
    due_date = django_filters.DateFromToRangeFilter(
        field_name='task__due_date')
    created_at_txt = django_filters.DateRangeFilter(
        field_name='task__created_at')
    due_date_txt = django_filters.DateRangeFilter(
        field_name='task__due_date')
    status = MultiChoiceFilter(field_name='task__status')
    importance = MultiChoiceFilter(field_name='task__importance')
    assigned_to = MultiChoiceFilter(field_name='task__assigned_to')
    workflow = MultiChoiceFilter(field_name='task__workflow_id')
    project = MultiChoiceFilter(field_name='task__workflow__project_id')
    workflow__isnull = filters.BooleanFilter(field_name='task__workflow',
                                             lookup_expr='isnull')
    tag = MultiChoiceTagFilter(field_name='task__task_tags__id')
    document_tags = MultiChoiceFilter(
        field_name='task__attachments__document_tags__id')
    document_tag = MultiChoiceTagFilter(
        field_name='task__attachments__document_tags__id')
    due_date__isnull = filters.BooleanFilter(field_name='task__due_date',
                                             lookup_expr='isnull')
    favorite_task = filters.BooleanFilter(field_name='is_favorite')
    private = filters.BooleanFilter(field_name='task__is_private')

    class Meta:
        model = TaskRank
        fields = []


class TaskStatisticFilterSet(filters.FilterSet):
    created_at = django_filters.DateFromToRangeFilter(
        field_name='created_at')
    due_date = django_filters.DateFromToRangeFilter(
        field_name='due_date')
    created_at_txt = django_filters.DateRangeFilter(
        field_name='created_at')
    due_date_txt = django_filters.DateRangeFilter(
        field_name='due_date')
    status = MultiChoiceFilter(field_name='status')
    importance = MultiChoiceFilter(field_name='importance')
    assigned_to = MultiChoiceFilter(field_name='assigned_to')
    workflow = MultiChoiceFilter(field_name='workflow_id')
    project = MultiChoiceFilter(field_name='workflow__project_id')

    class Meta:
        model = Task
        fields = []


class ProjectFilterSet(filters.FilterSet):
    created_at = django_filters.DateFromToRangeFilter(
        field_name='project__created_at')
    due_date = django_filters.DateFromToRangeFilter(
        field_name='project__due_date')
    created_at_txt = django_filters.DateRangeFilter(
        field_name='project__created_at')
    due_date_txt = django_filters.DateRangeFilter(
        field_name='project__due_date')
    status = MultiChoiceFilter(field_name='project__status')
    importance = MultiChoiceFilter(field_name='project__importance')
    tag = MultiChoiceTagFilter(field_name='project__project_tags__id')
    document_tags = MultiChoiceFilter(
        field_name='project__attachments__document_tags__id')
    document_tag = MultiChoiceTagFilter(
        field_name='project__attachments__document_tags__id')

    class Meta:
        model = ProjectRank
        fields = []


class WorkflowFilterSet(filters.FilterSet):
    created_at = django_filters.DateFromToRangeFilter(
        field_name='workflow__created_at')
    due_date = django_filters.DateFromToRangeFilter(
        field_name='workflow__due_date')
    created_at_txt = django_filters.DateRangeFilter(
        field_name='workflow__created_at')
    due_date_txt = django_filters.DateRangeFilter(
        field_name='workflow__due_date')
    project = MultiChoiceFilter(field_name='workflow__project_id')
    status = MultiChoiceFilter(field_name='workflow__status')
    importance = MultiChoiceFilter(field_name='workflow__importance')
    project__isnull = filters.BooleanFilter(field_name='workflow__project',
                                            lookup_expr='isnull')
    tag = MultiChoiceTagFilter(field_name='workflow__workflow_tags__id')
    document_tags = MultiChoiceFilter(
        field_name='workflow__attachments__document_tags__id')
    document_tag = MultiChoiceTagFilter(
        field_name='workflow__attachments__document_tags__id')

    class Meta:
        model = WorkflowRank
        fields = []


class AssignmentOverviewFilterSet(filters.FilterSet):
    user = MultiChoiceFilter(field_name='id')

    class Meta:
        model = User
        fields = []


class AuditHistoryFilterSet(filters.FilterSet):
    model_type = filters.ChoiceFilter(field_name="model_reference",
                                      lookup_expr='exact',
                                      choices=MODEL_CHOICES)
    model_id = MultiChoiceFilter(field_name='model_id')

    class Meta:
        model = AuditHistory
        fields = []


class TagFilterSet(filters.FilterSet):
    tag = MultiChoiceFilter(field_name='id')

    class Meta:
        model = Tag
        fields = []


class WorkGroupFilterSet(filters.FilterSet):
    user = MultiChoiceFilter(field_name='group_members__id')

    class Meta:
        model = WorkGroup
        fields = []


class CompanyWorkGroupFilterSet(filters.FilterSet):
    group = MultiChoiceFilter(field_name='id')
    group_member = MultiChoiceFilter(field_name='group_members__id')

    class Meta:
        model = WorkGroup
        fields = []


class SubmittedRequestFilterSet(filters.FilterSet):
    task = MultiChoiceFilter(field_name='task__status')
    project = MultiChoiceFilter(field_name='project__status')
    workflow = MultiChoiceFilter(field_name='workflow__status')

    class Meta:
        model = ServiceDeskExternalRequest
        fields = []


class PrivilageReportFilterSet(filters.FilterSet):
    changed_at = django_filters.DateFromToRangeFilter(
        field_name='changed_at')

    class Meta:
        model = Privilage_Change_Log
        fields = []


class TagReportFilterSet(filters.FilterSet):
    changed_at = django_filters.DateFromToRangeFilter(
        field_name='changed_at')

    class Meta:
        model = TagChangeLog
        fields = []


class GroupWorkLoadFilterSet(filters.FilterSet):
    changed_at = django_filters.DateFromToRangeFilter(
        field_name='changed_at')

    class Meta:
        model = GroupWorkLoadLog
        fields = []


class TeamMemberWorkLoadFilterSet(filters.FilterSet):
    changed_at = django_filters.DateFromToRangeFilter(
        field_name='changed_at')

    class Meta:
        model = TeamMemberWorkLoadLog
        fields = []


class WorkProductivityLogFilterSet(filters.FilterSet):
    created_on = django_filters.DateFromToRangeFilter(
        field_name='created_on')

    class Meta:
        model = WorkProductivityLog
        fields = []
