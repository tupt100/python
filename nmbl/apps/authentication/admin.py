import uuid

from django import forms
from django.contrib import admin
from django.contrib.admin.filters import AllValuesFieldListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as authGroup
from django.db import connection
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from notifications.models import UserNotificationSetting, \
    NotificationType

from .forms import InvitationAdminChangeForm, \
    InvitationAdminAddForm
from .models import (User, Organization, Invitation,
                     UserSetting, Group,
                     GroupAndPermission, Permission,
                     DefaultPermission,
                     UserLoginAttempt, AddUser,
                     CompanyInformation, IntroSlide,
                     UserIntroSlide)
from .utils import invitation_send


class DropdownFilter(AllValuesFieldListFilter):
    template = 'admin/dropdown_filter.html'


class InvitationAdmin(admin.ModelAdmin):
    add_form_template = 'admin/invitations/add_form.html'
    change_form_template = 'admin/invitations/invitation_change_form.html'
    list_display = ('email', 'sent', 'accepted', 'invited_by')

    # to remove *add invitation* button from admin site
    def has_add_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs['form'] = InvitationAdminChangeForm
        else:
            kwargs['form'] = InvitationAdminAddForm
            kwargs['form'].user = request.user
            kwargs['form'].request = request
        return super(InvitationAdmin, self).get_form(request, obj, **kwargs)


class AddUserAdmin(admin.ModelAdmin):
    add_form_template = 'admin/invitations/add_form.html'
    change_form_template = 'admin/invitations/invitation_change_form.html'
    list_display = ('email', 'sent', 'accepted', 'invited_by')

    # to remove *add invitation* button from admin site
    # def has_add_permission(self, request, obj=None):
    #     return False

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs['form'] = InvitationAdminChangeForm
        else:
            kwargs['form'] = InvitationAdminAddForm
            kwargs['form'].user = request.user
            kwargs['form'].request = request
        return super(AddUserAdmin, self).get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.key = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        company_owner = User.objects.filter(is_owner=True).first()
        obj.invited_by_company = company_owner.company
        obj.invited_by = company_owner
        obj.sent = timezone.now()

        in_app_notification_ids = list(
            NotificationType.objects.all().values_list(
                'id', flat=True)
        )
        obj.in_app_notification.set(in_app_notification_ids)
        obj.email_notification.set(in_app_notification_ids)
        super(AddUserAdmin, self).save_model(request, obj, form, change)
        invitation_send(company_owner, obj)

        # if change is False:
        #     full_endpoint_url = "{}{}{}{}".format(
        #         request.scheme,
        #         '://',
        #         request.META['HTTP_HOST'],
        #         '/api/send_bulk_invitation/send_bulk_invitation/')

        #     print("full_endpoint_url########", full_endpoint_url)
        #     in_app_notification_ids = list(
        #         NotificationType.objects.all().values_list(
        #             'id', flat=True)
        #     )
        #     email_notification_ids = in_app_notification_ids
        #     company_owner = User.objects.filter(is_owner=True).first()
        #     token_obj, created = Token.objects.get_or_create(
        #         user=company_owner)

        #     access_token = str(token_obj.key)

        #     payload = {
        #         "from_admin_invite_id": obj.id,
        #         "data": [{
        #             "email": obj.email,
        #             "title": obj.invited_by_group.name,
        #             "invited_by_group": obj.invited_by_group.id,
        #             "in_app_notification": in_app_notification_ids,
        #             "email_notification": email_notification_ids
        #         }]
        #     }
        #     requests.post(
        #         full_endpoint_url,
        #         data=json.dumps(payload),
        #         headers={
        #             'Content-Type': 'application/json',
        #             'Authorization': 'Token {}'.format(access_token)
        #         }
        #     )


class UserNotificationSettingAdminInline(admin.TabularInline):
    model = UserNotificationSetting
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class GroupAndPermissionAdmin(admin.ModelAdmin):
    list_display = ('group', 'permission', 'company',
                    'has_permission')
    list_filter = ('group', 'company', 'has_permission')


class DefaultPermissionAdmin(admin.ModelAdmin):
    list_display = ('group', 'permission', 'has_permission')
    list_filter = ('group', 'has_permission',
                   'permission__permission_category')


class UserAdmin(BaseUserAdmin):
    change_form_template = 'admin/user/user_change_form.html'

    fieldsets = (
        (None, {'fields': ('email', 'password', 'username')}),
        (_('Personal info'), {'fields': (
            'first_name', 'last_name', 'group',
            'company', 'key', 'title',
            'user_avatar')}),
        (_('Permissions'), {'fields': (
            'is_active', 'is_superuser', 'is_staff',
            'is_owner', 'is_delete')}),
        (_('Important dates'),
         {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    list_display = ["id", "email", "company", "is_active",
                    "is_owner", "date_joined", "last_login",
                    "group", ]

    list_filter = ('company', 'is_delete', 'group',)

    inlines = [UserNotificationSettingAdminInline]

    ordering = ('-id',)

    search_fields = ('first_name', 'last_name', 'email')


class OrganizationAdminForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "owner_name", "owner_email",
                  "company_address",
                  "city", "state", "country", "zip_code")

    def clean(self):
        cleaned_data = self.cleaned_data
        name = cleaned_data.get('name')
        owner_email = cleaned_data.get('owner_email')
        if Organization.objects.filter(name=name).exists():
            raise forms.ValidationError({
                "name": "This organisation is already registered"})
        if Organization.objects.filter(
                owner_email=owner_email).exists() or \
                User.objects.filter(email=owner_email).exists():
            raise forms.ValidationError({
                "owner_email": "This email is already registered"})
        return cleaned_data


class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = ["name", "owner_email", "company_address",
                    "city", "zip_code", "state", "country"]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('name', 'owner_email')
        return self.readonly_fields

    def has_add_permission(self, request):
        user = request.user
        if user.is_superuser and connection.schema_name != 'public' and \
                Organization.objects.count() == 0:
            return True
        else:
            return False


class PermissionAdminInline(admin.TabularInline):
    model = DefaultPermission
    extra = 1


class GroupAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "status", "organization"]
    inlines = [PermissionAdminInline]


class PermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "permission_category", "slug"]
    list_filter = ["permission_category", ]
    search_fields = ("name", "slug")


class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = (
        'company',
    )
    search_fields = (
        'company',
    )

    def get_queryset(self, request):
        user = request.user
        qs = super(CompanyInfoAdmin, self).get_queryset(request)
        if user.is_superuser and connection.schema_name != 'public':
            return qs
        return qs.none()

    def has_add_permission(self, request, obj=None):
        user = request.user
        if user.is_superuser and connection.schema_name != 'public' and \
                CompanyInformation.objects.count() == 0:
            return True
        return False


class UserLoginAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "is_failed", "attempt_ip", ]
    list_filter = ["user", "is_failed", ]
    search_fields = ("user", "slug")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class IntroSlideAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'module', 'rank',)
    list_filter = ('module',)


class UserIntroSlideAdmin(admin.ModelAdmin):
    list_display = ('user', 'slide', 'is_viewed',)
    list_filter = ('slide__module',)


admin.site.register(CompanyInformation, CompanyInfoAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Invitation, InvitationAdmin)
admin.site.register(AddUser, AddUserAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(UserSetting)
admin.site.unregister(authGroup)
admin.site.register(UserLoginAttempt, UserLoginAttemptAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Permission, PermissionAdmin)
admin.site.register(GroupAndPermission, GroupAndPermissionAdmin)
admin.site.register(DefaultPermission, DefaultPermissionAdmin)
admin.site.register(IntroSlide, IntroSlideAdmin)
admin.site.register(UserIntroSlide, UserIntroSlideAdmin)


class AuthenticationOrganization(ListView):
    model = Organization
    template_name = 'admin/authentication/organization.html'


class AuthenticationOrgPerm(DetailView):
    model = Organization
    template_name = 'admin/authentication/org_permission.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = Group.objects.all()
        context['permission'] = Permission.objects.all()
        context['group_permission'] = GroupAndPermission.objects.filter(
            company=context['object'])
        for grps in context['group']:
            for per in context['group_permission']:
                if grps.name == per.group.name:
                    gp = "<td>u</td>"
                    context['perm_dict'] = gp
        return context
