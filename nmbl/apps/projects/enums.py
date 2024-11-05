from django.utils.translation import gettext_lazy as _

# Importance level choices
IMPORTANCE_CHOICES = (
    (0, _("No importance")),
    (1, _("Low")),
    (2, _("Med")),
    (3, _("High")),
)


# Project/Workflow Status choices
PR_WF_STATUS_CHOICES = (
    (1, _("Active")),
    (2, _("Completed")),
    (3, _("Archived")),
    (4, _("External Request")),
    (5, _("External Update")),
)


def default_task_importance():
    return dict(High=0, Med=0, Low=0)
