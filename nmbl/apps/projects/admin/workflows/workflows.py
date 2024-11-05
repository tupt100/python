from django.contrib import admin
from projects.models import Workflow

from .abstract import WorkflowAbstractAdmin


class WorkflowAdmin(WorkflowAbstractAdmin):
    pass


admin.site.register(Workflow, WorkflowAdmin)
