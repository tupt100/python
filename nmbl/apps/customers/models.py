from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_tenants.models import TenantMixin, DomainMixin
from .features.models import *  # noqa


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until = models.DateField()
    on_trial = models.BooleanField()
    created_on = models.DateField(auto_now_add=True)
    owner_email = models.EmailField()
    owner_password = models.CharField(max_length=100)

    # default true, schema will be
    # automatically created and synced when it is saved
    auto_create_schema = True

    def __str__(self):
        return '{} - {}'.format(self.schema_name, self.name)

    def clean(self):
        super(Client, self).clean()
        if not self.schema_name.islower():
            raise ValidationError({
                'schema_name': [_('Schema name must be in lowercase.')]
            })


class Domain(DomainMixin):
    pass

    def __str__(self):
        return '{}'.format(self.domain)


class Postmark(models.Model):
    domain_name = models.ForeignKey(Domain,
                                    db_index=True,
                                    related_name='postmark_domain',
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.domain_name)
