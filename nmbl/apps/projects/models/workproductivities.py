from authentication.models import BaseModel
from django.db import models


class WorkProductivityLog(BaseModel):
    # model has been created to generate Productivity
    # report for Team Member
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
    team_member = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='team_member_productivity',
    )
    work_group = models.ForeignKey(
        'WorkGroup',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='group_productivity',
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_productivity',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_productivity',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_productivity',
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
    created_on = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
