from django.db.models.signals import pre_save

from notifications.models import Notification


def notification_pre_save(sender, instance, *args, **kwargs):
    """
    To save company name of user
    """
    if instance.user:
        if instance.user.company:
            instance.organization = instance.user.company


pre_save.connect(notification_pre_save, sender=Notification)
