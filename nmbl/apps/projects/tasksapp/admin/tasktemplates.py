# -*- coding: utf-8 -*-
from django.contrib import admin

from nmbl.apps.base.admin import BaseModelAdmin
from ..models import TaskTemplate, CustomField


class CustomFieldInline(admin.TabularInline):
    model = CustomField
    extra = 1


class TaskTemplateAdmin(BaseModelAdmin):
    fields = [
        'title',
        'created_by',
        'task_name',
        'importance',
        'workflow',
        'assigned_to',
        'assigned_to_group',
        'due_date',
        'start_date',
        'description',
        'is_private',
        'attorney_client_privilege',
        'work_product_privilege',
        'confidential_privilege',
    ]
    list_display = [
        'title',
        'created_by',
    ]
    list_filter = []
    search_fields = [
        'title',
    ]
    exclude = [
        'fields',
    ]
    raw_id_fields = [
        'created_by',
        'workflow',
        'assigned_to',
        'assigned_to_group',
    ]
    readonly_fields = []
    allowed_actions = []
    inlines = [
        CustomFieldInline,
    ]

    def __init__(self, *args, **kwargs):
        klass = TaskTemplateAdmin
        klass_parent = BaseModelAdmin

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


admin.site.register(TaskTemplate, TaskTemplateAdmin)
