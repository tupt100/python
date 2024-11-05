from authentication.models import (DefaultPermission,
                                   GroupAndPermission,
                                   Organization)

# GroupAndPermission.truncate()
for organization in Organization.objects.all():
    for default_permission in DefaultPermission.objects.all():
        try:
            GroupAndPermission.objects.create(
                company=organization,
                group=default_permission.group,
                permission=default_permission.permission,
                has_permission=default_permission.has_permission,
            )
        except Exception as e:
            print(e)
