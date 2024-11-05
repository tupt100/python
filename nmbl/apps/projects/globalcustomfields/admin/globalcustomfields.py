import json

from django.contrib import admin
from django import forms
from django.contrib.contenttypes.models import ContentType
from base.admin import BaseModelAdmin
from ..models import GlobalCustomField, GlobalCustomFieldAllowedType


class GlobalCustomFieldForm(forms.ModelForm):
    allow_content_type = forms.MultipleChoiceField(
        choices=GlobalCustomFieldAllowedType.choices_content_type,
        required=True,
        widget=forms.CheckboxSelectMultiple())

    class Meta:
        model = GlobalCustomField
        fields = '__all__'


class GlobalCustomFieldAdmin(BaseModelAdmin):
    fields = [
        'label',
        'created_by',
        'field_type',
        'default_value',
        'is_required',
        'description',
        'is_archive',
        'allow_content_type'

    ]
    list_display = [
        'label',
        'created_by',
        'field_type',
        'default_value',
        'is_required',
        'description',
        'is_archive',
        'allow_content_type'
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
        'created_by',
    ]
    readonly_fields = []
    allowed_actions = []
    inlines = []
    form = GlobalCustomFieldForm

    def __init__(self, *args, **kwargs):
        klass = GlobalCustomFieldAdmin
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


admin.site.register(GlobalCustomField, GlobalCustomFieldAdmin)
