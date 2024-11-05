from authentication.models import BaseModel
from django.db import models
from django.utils.translation import gettext_lazy as _


class PageInstruction(BaseModel):
    instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Instructions'),
    )
