from django.contrib import admin
from projects.models import TaskFixture

from .abstract import TaskAbstractAdmin


class TaskFixtureAdmin(TaskAbstractAdmin):
    raw_id_fields = ('workflow_template',)


admin.site.register(TaskFixture, TaskFixtureAdmin)
