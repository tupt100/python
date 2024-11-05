from authentication.models import BaseModel
from django.db import models


class GroupWorkLoadLog(BaseModel):
    # model has been created to generate Workload report for Group
    CATEGORY_TYPES = (
        ("project", "Project"),
        ("workflow", "Workflow"),
        ("task", "Task"),
    )
    category_type = models.CharField(
        choices=CATEGORY_TYPES,
        null=True,
        blank=True,
        max_length=225,
    )
    work_group = models.ForeignKey(
        'WorkGroup',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='group_workload',
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_workload',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_workload',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_workload',
    )
    new = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
    completed = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
    changed_at = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
    group_name = models.CharField(
        null=True,
        blank=True,
        max_length=225,
    )
