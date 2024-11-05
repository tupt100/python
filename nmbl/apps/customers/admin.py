from django.contrib import admin
from django.db import connection

from .features import *  # noqa
from .models import Client, Domain, Postmark, Feature


class FeatureClientAdminInline(admin.TabularInline):
    fields = ('id', 'key', 'value', )
    model = Feature
    extra = 0
    max_num = 0
    exclude = ('is_active',)
    readonly_fields = ('key', 'id', )
    can_delete = False


class ClientAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'paid_until',
        'on_trial', 'created_on', 'owner_email',
        'schema_name',
    )
    search_fields = (
        'owner_email', 'name',
    )
    inlines = (FeatureClientAdminInline,)

    class Media:
        css = {"all": ("css/hide_admin_original.css",)}

    def get_queryset(self, request):
        print("NAME#", connection.schema_name)
        qs = super(ClientAdmin, self).get_queryset(request)
        if request.user.is_superuser and \
                connection.schema_name == 'public':
            return qs
        return qs.none()

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser and \
                connection.schema_name == 'public':
            return True
        return False


admin.site.register(Client, ClientAdmin)


class DomainAdmin(admin.ModelAdmin):
    list_display = (
        'domain', 'is_primary',
    )
    search_fields = (
        'domain',
    )

    def get_queryset(self, request):
        print("NAME#", connection.schema_name)
        qs = super(DomainAdmin, self).get_queryset(request)
        if request.user.is_superuser and \
                connection.schema_name == 'public':
            return qs
        return qs.none()

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser and connection.schema_name == 'public':
            return True
        return False


class PostmarkAdmin(admin.ModelAdmin):

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser and \
                connection.schema_name == 'public':
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Domain, DomainAdmin)
admin.site.register(Postmark, PostmarkAdmin)
