from django.contrib import admin
from ..models import WorkflowTemplate
from .basetemplates import BaseTemplateAdmin


# TODO: handle `assigned_to_users` and `custom fields` inline for many to many
class WorkflowTemplateAdmin(BaseTemplateAdmin):
    fields = [
        'project',
        'assigned_to_users',
    ]
    list_display = [
    ]
    list_filter = []
    search_fields = [
    ]
    exclude = [
    ]
    raw_id_fields = [
        'project',
    ]
    readonly_fields = []
    allowed_actions = []
    inlines = [
    ]

    def __init__(self, *args, **kwargs):
        klass = WorkflowTemplateAdmin
        klass_parent = BaseTemplateAdmin

        super(klass, self).__init__(*args, **kwargs)

        self.fields = klass_parent.fields + self.fields
        self.list_display = klass_parent.list_display + self.list_display
        self.list_filter = klass_parent.list_filter + self.list_filter
        self.search_fields = klass_parent.search_fields + self.search_fields
        self.exclude = klass_parent.exclude + self.exclude
        self.raw_id_fields = klass_parent.raw_id_fields + self.raw_id_fields
        self.readonly_fields = klass_parent.readonly_fields + self.readonly_fields
        self.allowed_actions = klass_parent.allowed_actions + self.allowed_actions
        self.inlines = klass_parent.inlines + self.inlines


admin.site.register(WorkflowTemplate, WorkflowTemplateAdmin)
