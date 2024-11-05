from authentication.models import BaseModel, BaseNameModel
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class WorkGroup(BaseNameModel):
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='work_group_organization',
        verbose_name=_('WorkGroup Company'),
    )
    group_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='WorkGroupMember',
        blank=True,
        related_name='workgroup_assigned_to_users',
    )

    class Meta:
        unique_together = ["name", "organization"]

    def __str__(self):
        return str(self.name)


class WorkGroupMember(BaseModel):
    work_group = models.ForeignKey(
        'WorkGroup',
        on_delete=models.CASCADE,
        related_name='work_group',
        verbose_name=_('WorkGroup'),
    )
    group_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='workgroup_assigned_to_user',
        verbose_name=_('Work Group Member'),
    )
