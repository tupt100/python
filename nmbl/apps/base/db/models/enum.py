import django

if django.__version__ >= '3.0':
    from django.db import models

    TextChoices = models.TextChoices
    IntegerChoices = models.IntegerChoices
else:
    from .enumdjango import TextChoices as ETextChoices, IntegerChoices as EIntegerChoices

    TextChoices = ETextChoices
    IntegerChoices = EIntegerChoices
