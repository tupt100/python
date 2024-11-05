from django.contrib import admin

from base.admin import BaseModelAdmin
from ..models import TemplateCustomField


class TemplateCustomFieldAdmin(BaseModelAdmin):
    fields = [
        'label',
        'field_type',
        'default_value',
        'is_required',
        'description',
        'object_id',
        'content_type',
    ]
    list_display = [
        'label',
        'field_type',
        'default_value',
        'is_required',
        'description',
        'object_id',
        'content_type',
    ]
    list_filter = [
        'field_type',
        'is_required',
    ]
    search_fields = [
        'label',
        'default_value',
        'description',
    ]
    exclude = []
    raw_id_fields = [
    ]
    readonly_fields = []
    allowed_actions = []
    inlines = []

    def __init__(self, *args, **kwargs):
        klass = TemplateCustomFieldAdmin
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


admin.site.register(TemplateCustomField, TemplateCustomFieldAdmin)
