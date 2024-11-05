from django.contrib import admin
from django import forms
from django.contrib.contenttypes.models import ContentType

from base.admin import BaseModelAdmin
from ..models import GlobalCustomFieldValue, GlobalCustomFieldAllowedType


class GlobalCustomFieldValueForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(GlobalCustomFieldValueForm, self).__init__(*args, **kwargs)

        self.fields['content_type'].queryset = ContentType.objects.filter(
            pk__in=GlobalCustomFieldAllowedType.content_type_values)


class GlobalCustomFieldValueAdmin(BaseModelAdmin):
    fields = [
        'global_custom_field',
        'content_type',
        'object_id',
        'value',
        'is_archive',
    ]
    list_display = [
        'global_custom_field',
        'content_type',
        'object_id',
        'value',
        'is_archive',
    ]
    list_filter = [
        'content_type',
        'is_archive',
    ]
    search_fields = [
        'global_custom_field',
        'object_id',
    ]
    exclude = []
    raw_id_fields = [
    ]
    readonly_fields = []
    allowed_actions = []
    inlines = []
    form = GlobalCustomFieldValueForm

    def __init__(self, *args, **kwargs):
        klass = GlobalCustomFieldValueAdmin
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


admin.site.register(GlobalCustomFieldValue, GlobalCustomFieldValueAdmin)
