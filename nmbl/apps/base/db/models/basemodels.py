from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Q
from django.utils.translation import gettext_lazy as _


"""
BaseModel
"""


class BaseModelQuerySet(models.QuerySet):
    def __init__(self, *args, **kwargs):
        super(BaseModelQuerySet, self).__init__(*args, **kwargs)

    def active(self):
        return self.filter(
            is_active=True
        )


class BaseModelManager(models.Manager):
    def get_queryset(self):
        return BaseModelQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()


class BaseModel(models.Model):
    """Abstract model to Track the creation/updated date for a model."""
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    update_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return '{}'.format(self.pk)

    def save(self, *args, **kwargs):
        self.full_clean()
        super(BaseModel, self).save(*args, **kwargs)
