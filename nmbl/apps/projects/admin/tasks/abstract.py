import json

from django import forms
from django.contrib import admin


class TaskAbstractAdminForm(forms.ModelForm):
    def clean_custom_fields_value(self):
        Model = self._meta.model
        _mutable = self.data._mutable
        # set to mutable
        self.data._mutable = True
        custom_fields_value = Model.prepare_custom_fields_value_task(
            self.cleaned_data.get('task_template'), self.cleaned_data.get('custom_fields_value')
        )
        self.data['custom_fields_value'] = json.dumps(custom_fields_value)
        self.data._mutable = _mutable
        return custom_fields_value


class TaskAbstractAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "due_date",
        "importance",
        "status",
        "organization",
        'task_template',
        "created_at",
    ]
    list_filter = ['importance', "status", "organization"]
    search_fields = ["id", "name"]
    raw_id_fields = [
        'task_template',
    ]
    form = TaskAbstractAdminForm
    save_as = True
