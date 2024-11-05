from authentication.models import BaseModel
from django.db import models


class CompletionLog(BaseModel):
    # model has been created to generate Efficiency
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
        related_name='completed_by_team_member',
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_completion',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_completion',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_completion',
    )
    # calculate to total time(in days) spent on
    # task/project/workflow to complete it
    completion_time = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
    created_on = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
    completed_on = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
