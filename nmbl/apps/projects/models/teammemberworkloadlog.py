from authentication.models import BaseModel
from django.db import models


class TeamMemberWorkLoadLog(BaseModel):
    # model has been created to generate Workload report for Team Member
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
        related_name='team_member_workload',
    )
    new = models.IntegerField(
        default=0,
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_team_member_workload',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_team_member_workload',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_team_member_workload',
    )
    changed_at = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
