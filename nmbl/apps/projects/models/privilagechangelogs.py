from authentication.models import BaseModel
from django.contrib.postgres.fields import JSONField
from django.db import models


# TODO: refactor this model class name!
class Privilage_Change_Log(BaseModel):
    # model has been created to generate Privilege report
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
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_privilege',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_privilege',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_privilege',
    )
    team_member = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='team_member_privilege',
    )
    old_privilege = JSONField(
        blank=True,
        null=True,
    )
    new_privilege = JSONField(
        blank=True,
        null=True,
    )
    changed_at = models.DateField(
        db_index=True,
        null=True,
        blank=True,
    )
    changed_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='changed_privilege_by',
    )
