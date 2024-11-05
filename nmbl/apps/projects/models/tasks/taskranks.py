from django.db import connection, models


class TaskRank(models.Model):
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
    )
    task = models.ForeignKey(
        'Task',
        on_delete=models.CASCADE,
    )
    rank = models.PositiveIntegerField(
        default=1,
    )
    is_active = models.BooleanField(
        default=True,
    )
    is_favorite = models.BooleanField(
        default=False,
    )

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))
