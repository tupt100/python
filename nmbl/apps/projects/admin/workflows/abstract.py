from django.contrib import admin


class WorkflowAbstractAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "due_date", "status", "importance", "task_importance"]
    list_filter = ["organization", "status"]
    search_fields = ["id", "name"]
