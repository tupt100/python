from authentication.models import BaseModel
from django.db import models
from django.utils.translation import gettext_lazy as _


class Tag(BaseModel):
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='tag_organization',
        verbose_name=_('Organization Tag'),
    )
    tag = models.CharField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name=_('Tag'),
    )

    def __str__(self):
        return str(self.tag)
