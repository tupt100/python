import base64
import imghdr
import uuid

import six
from django.core.files.base import ContentFile
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import (Organization, User, Permission,
                     UserSetting, Invitation,
                     Group, GroupAndPermission,
                     DefaultPermission, CompanyInformation,
                     UserIntroSlide, IntroSlide, PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES)


class NewCompanySignUpSerializer(serializers.Serializer):
    first_name = serializers.EmailField()
    last_name = serializers.EmailField()
    password = serializers.CharField()
    confirm_password = serializers.CharField()


class CompanySignUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('id', 'owner_email', 'owner_name')

        read_only_fields = ('id',)


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'password')


class LoginAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'password')
        extra_kwargs = {
            'email': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this email field",
                }
            },
            'password': {
                'required': True,
                'error_messages': {
                    'required': "Please fill this password field",
                }
            },
        }


class ShowGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name', 'is_user_specific', 'is_public',
                  'is_company_admin')


class BasicGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name',)


class ShowUserSerializer(serializers.ModelSerializer):
    work_group = serializers.SerializerMethodField()
    group = BasicGroupSerializer()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'group',
                  'title', 'is_owner', 'work_group',)
        read_only_fields = ('group', 'work_group',)

    def get_work_group(self, obj):
        from projects.serializers import CompanyWorkGroupBasicSerializer
        from projects.models import WorkGroup
        return CompanyWorkGroupBasicSerializer(
            WorkGroup.objects.filter(organization=obj.company,
                                     group_members=obj), many=True
        ).data


class UserSerializer(serializers.ModelSerializer):
    group = ShowGroupSerializer()

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name',
                  'last_name', 'email', 'group',
                  'company', 'title', 'is_owner',
                  'user_avatar')
        read_only_fields = ('username', 'email',
                            'group', 'company')

    def get_user_avatar(self, user):
        request = self.context.get("request")
        if user.user_avatar:
            try:
                # this is causing issue while login(
                # just hot fixed for temporary)
                user_avatar_url = user.user_avatar.url
                return request.build_absolute_uri(user_avatar_url)
            except Exception as e:
                print("exception:", e)
                return None
        else:
            return None


class UpdateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email',
                  'group', 'title')
        read_only_fields = ('email',)


class ShowPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ('id', 'name', 'slug')


class UserInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ('id', 'email', 'invited_by_group', 'title',
                  'first_name', 'last_name',)


class InvitationGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name',)


class InvitationListSerializer(serializers.ModelSerializer):
    invited_by_group = InvitationGroupSerializer(read_only=True)

    class Meta:
        model = Invitation
        fields = ('id', 'first_name', 'last_name',
                  'invited_by_group', 'title',)
        read_only_fields = ('id',)


class InvitationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ('id', 'first_name', 'last_name',
                  'invited_by_group', 'title',)
        read_only_fields = ('id',)


class ChangeGroupSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    group_id = serializers.IntegerField()


class UserSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSetting
        fields = ('id', 'setting',)


class ShowSentInvitationSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Invitation
        fields = ['id', 'email', 'accepted', 'sent']


class ListCompanyActiveUsersSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = User
        fields = ['id', 'email']


class ListPendingInvitationSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Invitation
        fields = ['id', 'email', 'invited_by_group', 'title',
                  'email_notification', 'in_app_notification']


class ResetPasswordSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(
        allow_blank=False, write_only=True)

    class Meta:
        model = User
        fields = ('password', 'confirm_password')

    def validate(self, validated_data):
        password = validated_data.get('password')
        confirm_password = validated_data.pop('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError("Those passwords don't match.")
        return validated_data


class MyPermissionSerializer(serializers.ModelSerializer):
    permission_slug = serializers.SerializerMethodField()
    model_type = serializers.SerializerMethodField()

    class Meta:
        model = GroupAndPermission
        fields = ('permission_slug', 'model_type')

    def get_permission_slug(self, obj):
        return obj.permission.slug

    def get_model_type(self, obj):
        return obj.permission.permission_category


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    class Meta:
        fields = ('current_password', 'new_password')


class OrganizationGroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'
        extra_kwargs = {
            "name": {
                "required": True
            }
        }

    def validate(self, attrs):
        request = self.context['request']
        attrs['organization'] = request.user.company
        return attrs


class Base64ImageField(serializers.ImageField):
    """
    Decode Base64 to Image.
    """

    def to_internal_value(self, data):
        if isinstance(data, six.string_types):
            if 'data:' in data and ';base64,' in data:
                header, data = data.split(';base64,')
            try:
                decoded_file = base64.b64decode(data)
            except TypeError:
                self.fail('invalid_image')

            # unique file name
            file_name = str(uuid.uuid4())[:12]
            # file extension
            file_extension = self.get_file_extension(file_name, decoded_file)
            # file name with extension
            complete_file_name = "%s.%s" % (file_name, file_extension,)
            data = ContentFile(decoded_file, name=complete_file_name)
        return super(Base64ImageField, self).to_internal_value(data)

    def get_file_extension(self, file_name, decoded_file):
        extension = imghdr.what(file_name, decoded_file)
        extension = "jpg" if extension == "jpeg" else extension

        return extension


class UserAvatarUploadSerializer(serializers.ModelSerializer):
    """
    Serializer class for uploading/updating user avatar.
    """
    user_avatar = Base64ImageField(
        max_length=None, use_url=True,
    )

    class Meta:
        model = User
        fields = ('user_avatar',)

    def validate(self, attrs):
        request = self.context.get('request')
        if not request.user.company:
            raise serializers.ValidationError(
                {"detail": "You are not part of any \
                organisation,So you can't upload Avatar."})
        return attrs


class GroupAndPermissionManagerSerializer(serializers.ModelSerializer):
    """
    serializer class for permission information in permission manager.
    """
    name = serializers.CharField(source='permission.name')
    slug = serializers.CharField(source='permission.slug')
    id = serializers.IntegerField(source='permission.id')

    class Meta:
        model = GroupAndPermission
        fields = ('id', 'name', 'slug')
        depth = 1


class UserInformationPermissionManagerSerializer(serializers.ModelSerializer):
    """
    serializer class for User information in PermissionManager.
    """

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'title')


class PermissionManagerListSerializer(serializers.ModelSerializer):
    """
    Serializer class to respond with information needed for Permission Manager
    section.
    """
    users_count = serializers.IntegerField()
    total_permissions = serializers.SerializerMethodField()
    has_permissions = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id',
            'name',
            'users_count',
            'total_permissions',
            'has_permissions',
            'user_details',
            'can_be_delete',
        ]

    def to_representation(self, data):
        iterable = super(PermissionManagerListSerializer, self).to_representation(data)
        iterable.update(iterable.pop('total_permissions'))
        iterable.update(iterable.pop('has_permissions'))
        return iterable

    def get_total_permissions(self, obj):
        items = {}
        for key, value in PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES():
            count = Permission.objects.all().filter(
                permission_category=key).count()
            items[f'total_{key}_permissions'] = count
        return items

    def get_has_permissions(self, obj):
        items = {}
        for key, value in PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES():
            count = obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category=key,
                has_permission=True).count()
            items[f'has_{key}_permissions'] = count
        return items

    # get User details from User table.
    def get_user_details(self, obj):
        return UserInformationPermissionManagerSerializer(
            obj.user_group.all().filter(
                company=self.company, is_delete=False), many=True).data

    @property
    def company(self):
        return self.context.get('request').user.company


class PermissionManagerUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer class to update Group permissions under Permission Manager tab.
    """
    try:
        min_order = Permission.objects.all().order_by("id").first()
        max_order = Permission.objects.all().order_by("-id").first()
    except Exception as e:
        print("exception:", e)
        min_order = None
        max_order = None
    min_value = 0
    max_value = 0
    if min_order:
        min_value = min_order.id
    if max_order:
        max_value = max_order.id
    default_permissions = serializers.ListField(
        child=serializers.IntegerField(min_value=min_value,
                                       max_value=max_value), )

    class Meta:
        model = Group
        fields = ("default_permissions",)

    def validate(self, data):
        default_permission_list = data.get("default_permissions")
        # check if duplicate ids are passed  in the default_permissions list
        if len(default_permission_list) != len(set(default_permission_list)):
            raise ValidationError({
                "details": "Duplicate Permission IDs are passed in request."
            })
        # check all the default permission ids passed exist in the system.
        all_permission_list = list(Permission.objects.all()
                                   .values_list('pk', flat=True))
        if not (set(default_permission_list).issubset(
                set(all_permission_list))):
            raise ValidationError({
                "details": "Incorrect Permission IDs are passed."
            })
        return data

    def update(self, instance, validated_data):
        # Delete existing entries for the group object in DefaluPermission &
        # GroupAndPermission Tables.
        DefaultPermission.objects.filter(group=instance).delete()
        GroupAndPermission.objects.filter(group=instance).delete()
        # create entries in DefaultPermission & GroupAndPermission Models.
        permission_objs_qs = Permission.objects.filter(
            id__in=validated_data.get('default_permissions'))
        for permission_obj in permission_objs_qs:
            DefaultPermission.objects.create(
                group=instance,
                permission=permission_obj,
                has_permission=True
            )
            GroupAndPermission.objects.create(
                group=instance,
                permission=permission_obj,
                company=self.context.get('request').user.company,
                has_permission=True
            )
        # check if group has view all and view mine both permission
        # enable then remove view mine permission
        if GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True,
                permission__slug='task_task-view-all').exists() \
                and GroupAndPermission.objects.filter(
            group=instance, company=instance.organization,
            has_permission=True, permission__slug='task_task-view'
        ).exists():
            GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True,
                permission__slug='task_task-view').delete()
        if GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True,
                permission__slug='project_project-view-all').exists() \
                and GroupAndPermission.objects.filter(
            group=instance, company=instance.organization,
            has_permission=True, permission__slug='project_project-view'
        ).exists():
            GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True,
                permission__slug='project_project-view').delete()
        if GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True,
                permission__slug='workflow_workflow-view-all').exists() \
                and GroupAndPermission.objects.filter(
            group=instance, company=instance.organization,
            has_permission=True, permission__slug='workflow_workflow-view'
        ).exists():
            GroupAndPermission.objects.filter(
                group=instance, company=instance.organization,
                has_permission=True, permission__slug='workflow_workflow-view'
            ).delete()
        from projects.tasks import permission_group_update
        permission_group_update(instance)
        return instance


class CompanyInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyInformation
        fields = ('logo_url', 'message', 'company', 'background_color',)

    company = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    def get_company(self, obj):
        return Organization.objects.first().name

    def get_logo_url(self, obj):
        if obj.logo:
            return self.context['request'].build_absolute_uri(obj.logo.url)
        else:
            return None


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name',
                  'user_avatar_thumb',)

    user_avatar_thumb = serializers.SerializerMethodField()

    def get_user_avatar_thumb(self, user):
        request = self.context.get("request")
        if user.user_avatar_thumb:
            try:
                user_avatar_thumb_url = user.user_avatar_thumb.url
                return request.build_absolute_uri(user_avatar_thumb_url)
            except Exception as e:
                print("exception:", e)
                return None
        else:
            return None


class GroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name',)


class UserDetailUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'title',)


class UserGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('name', 'is_company_admin',)


class UserDetailSerializer(serializers.ModelSerializer):
    group = UserGroupSerializer()
    has_request_permission = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email',
                  'group', 'title', 'is_owner',
                  'user_avatar', 'has_request_permission',)

    def get_user_avatar(self, user):
        request = self.context.get("request")
        if user.user_avatar:
            try:
                user_avatar_url = user.user_avatar.url
                return request.build_absolute_uri(user_avatar_url)
            except Exception as e:
                print("exception:", e)
                return None
        else:
            return None

    def get_has_request_permission(self, user):
        request = self.context.get("request")
        user = request.user
        group = user.group
        company = user.company
        if GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category='request',
                permission__slug='request_request-view',
                has_permission=True).exists():
            return True
        else:
            return False


class GroupDetailSerializer(serializers.ModelSerializer):
    project_permission = serializers.SerializerMethodField()
    task_permission = serializers.SerializerMethodField()
    workflow_permission = serializers.SerializerMethodField()
    request_permission = serializers.SerializerMethodField()
    tasktemplate_permission = serializers.SerializerMethodField()
    globalcustomfield_permission = serializers.SerializerMethodField()
    workflowtemplate_permission = serializers.SerializerMethodField()
    projecttemplate_permission = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id',
            'name',
            'project_permission',
            'task_permission',
            'workflow_permission',
            'request_permission',
            'tasktemplate_permission',
            'globalcustomfield_permission',
            'workflowtemplate_permission',
            'projecttemplate_permission',
        ]

    @property
    def company(self):
        return self.context.get('request').user.company

    # get workflow permission details from the permission table.
    def get_workflow_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="workflow",
                has_permission=True),
            many=True).data

    # get project permission details from the permission table.
    def get_project_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="project",
                has_permission=True),
            many=True).data

    # get request permission details from the permission table.
    def get_request_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="request",
                has_permission=True),
            many=True).data

    # get task permission details from the permission table.
    def get_task_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="task",
                has_permission=True),
            many=True).data

    # get task template permission details from the permission table.
    def get_tasktemplate_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="tasktemplate",
                has_permission=True),
            many=True).data

    # get global custom field permission details from the permission table.
    def get_globalcustomfield_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="globalcustomfield",
                has_permission=True),
            many=True).data

    # get workflow template permission details from the permission table.
    def get_workflowtemplate_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="workflowtemplate",
                has_permission=True),
            many=True).data

    # get project template permission details from the permission table.
    def get_projecttemplate_permission(self, obj):
        return GroupAndPermissionManagerSerializer(
            obj.group_permission.all().filter(
                company=self.company,
                permission__permission_category="projecttemplate",
                has_permission=True),
            many=True).data


class InvitationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ('first_name', 'last_name', 'email',)


class IntroSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntroSlide
        fields = ('title', 'message', 'image', 'rank',)


class UserIntroSlideSerializer(serializers.ModelSerializer):
    slide = IntroSlideSerializer(read_only=True)

    class Meta:
        model = UserIntroSlide
        fields = ('slide', 'is_viewed',)
