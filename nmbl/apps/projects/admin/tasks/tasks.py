from django.contrib import admin
from projects.models import Task

from .abstract import TaskAbstractAdmin


class TaskAdmin(TaskAbstractAdmin):
    raw_id_fields = (
        'workflow',
        'task_template',
    )


admin.site.register(Task, TaskAdmin)
