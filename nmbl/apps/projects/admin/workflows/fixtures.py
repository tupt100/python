from django.contrib import admin
from projects.models import WorkflowFixture

from .abstract import WorkflowAbstractAdmin


class WorkflowFixtureAdmin(WorkflowAbstractAdmin):
    pass


admin.site.register(WorkflowFixture, WorkflowFixtureAdmin)
