from django.db import connection, models


class WorkflowRank(models.Model):
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
    )
    workflow = models.ForeignKey(
        'Workflow',
        on_delete=models.CASCADE,
    )
    rank = models.PositiveIntegerField(
        default=1,
    )
    is_active = models.BooleanField(
        default=True,
    )

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))
