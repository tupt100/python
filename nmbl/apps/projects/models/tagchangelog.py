from authentication.models import BaseModel
from django.db import models


class TagChangeLog(BaseModel):
    # model has been created to generate Tag report
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
    tag = models.CharField(
        null=True,
        blank=True,
        max_length=225,
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
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_tag',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_tag',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_tag',
    )
    tag_reference = models.ForeignKey(
        'Tag',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tag_log',
    )
