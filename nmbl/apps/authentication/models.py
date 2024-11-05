import datetime
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, connection
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from easy_thumbnails.fields import ThumbnailerImageField

from . import signals
from .adapters import get_invitations_adapter
from .app_settings import app_settings
from .managers import BaseInvitationManager, UserManager
from customers.models import Feature, FeatureName

GROUPS_STATUS_CHOICES = (
    ('active', _("Active")),
    ('inactive', _("Inactive"))
)

STATUS_CHOICES = (
    (1, _("Unread")),
    (2, _("Read"))
)

PERMISSION_CATEGORY_CHOICES = (
    ('task', _("Task")),
    ('workflow', _("Workflow")),
    ('project', _("Project")),
    ('request', _("Request")),
    ('tasktemplate', _("Task template")),
    ('globalcustomfield', _("Global custom field")),
    ('workflowtemplate', _("Workflow template")),
    ('projecttemplate', _("Project template"))
)

CROP_SETTINGS = {'size': (170, 170), 'crop': 'smart'}
THUMB_CROP_SETTINGS = {'size': (50, 50), 'crop': 'smart'}


def PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES():
    p = set(map(lambda x: x[0].upper(), PERMISSION_CATEGORY_CHOICES))
    fn = set(FeatureName.values)
    p_temp = p - fn
    fintersection = p.intersection(fn)
    p_temp = p_temp.union(
        set(
            Feature.objects.active().filter(key__in=fintersection, value=True).values_list('key', flat=True)
        )
    )
    return tuple(filter(lambda x: x[0].upper() in p_temp, PERMISSION_CATEGORY_CHOICES))


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,
                                      db_index=True,
                                      verbose_name=_('Created At'))
    modified_at = models.DateTimeField(auto_now=True,
                                       db_index=True,
                                       verbose_name=_('Modified At'))

    class Meta:
        abstract = True


class BaseNameModel(BaseModel):
    name = models.CharField(max_length=254, db_index=True,
                            verbose_name=_('Name'))

    class Meta:
        abstract = True


class Permission(BaseModel):
    name = models.CharField(max_length=254, db_index=True,
                            verbose_name=_('Name'))
    permission_category = models.CharField(
        max_length=20, verbose_name=_('Permission Category'),
        choices=PERMISSION_CATEGORY_CHOICES)
    slug = models.SlugField(unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):

        # replacing "/" in create/edit permission with " "
        if "/" in self.name:
            self.slug = slugify(self.permission_category + "_" +
                                self.name.replace("/", " "))
        else:
            self.slug = slugify(self.permission_category + "_" + self.name)
        super(Permission, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.permission_category + "-" + self.name)


class Organization(BaseModel):
    name = models.CharField(max_length=254, unique=True, db_index=True,
                            verbose_name=_('Company Name'))
    company_address = models.TextField(verbose_name=_('Organization Address'),
                                       null=True, blank=True)
    city = models.CharField(verbose_name=_('Organization City'), null=True,
                            blank=True, max_length=255)
    zip_code = models.CharField(verbose_name=_('Organization Zip Code'),
                                null=True, blank=True, max_length=255)
    state = models.CharField(verbose_name=_('Organization State'), null=True,
                             blank=True, max_length=255)
    country = models.CharField(verbose_name=_('Organization Country'),
                               null=True, blank=True, max_length=255)
    owner_email = models.EmailField(verbose_name=_('Owner E-mail Address'),
                                    max_length=254)
    owner_name = models.CharField(max_length=254, verbose_name=_('Owner Name'))

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse('organization-permission', kwargs={'pk': self.pk})


class Group(BaseNameModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     verbose_name=_('Organization Group'),
                                     related_name='organizationgroup_company',
                                     null=True, blank=True)
    status = models.CharField(max_length=20, verbose_name=_('Group Status'),
                              choices=GROUPS_STATUS_CHOICES, default='active')
    default_permissions = models.ManyToManyField(
        Permission, through='DefaultPermission',
        related_name='default_permissions')
    is_public = models.BooleanField(verbose_name=_('Is Public'),
                                    default=False)
    # is a role specific to user.
    is_user_specific = models.BooleanField(
        verbose_name="Is User Specific Role", default=False)
    # users_count = models.IntegerField(verbose_name=_('User count'),
    # default=0)
    is_company_admin = models.BooleanField(verbose_name=_('Is Company Admin'),
                                           default=False)
    can_be_delete = models.BooleanField(verbose_name=_('Can Be Delete'),
                                        default=True)

    def __str__(self):
        return str(self.name)


class DefaultPermission(BaseModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              verbose_name=_('Group'),
                              related_name='default_permission_group')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE,
                                   verbose_name=_('Group Permission'),
                                   related_name='default_permission_permission'
                                   )
    has_permission = models.BooleanField(verbose_name=_('Has Permission'),
                                         default=False)

    class Meta:
        unique_together = ["group", "permission"]


class User(AbstractUser, BaseModel):
    first_name = models.CharField(max_length=254, db_index=True,
                                  verbose_name=_('First Name'))
    last_name = models.CharField(max_length=254, db_index=True,
                                 verbose_name=_('Last Name'))
    email = models.EmailField(max_length=255, unique=True, db_index=True)
    group = models.ForeignKey(Group, null=True, blank=True,
                              on_delete=models.SET_NULL,
                              related_name='user_group')
    company = models.ForeignKey(Organization, null=True, blank=True,
                                on_delete=models.CASCADE,
                                related_name='user_company')
    key = models.CharField(verbose_name=_('Key'), max_length=64, unique=True,
                           null=True, blank=True)

    title = models.CharField(max_length=254,
                             verbose_name=_('Title'), null=True,
                             blank=True)
    is_owner = models.BooleanField(verbose_name=_('Is owner status'),
                                   default=False)
    is_delete = models.BooleanField(verbose_name=_('Is Delete'),
                                    default=False)
    # user avatar
    user_avatar = ThumbnailerImageField(null=True, blank=True,
                                        upload_to='Profiles/%Y/%m/',
                                        verbose_name='Avatar',
                                        resize_source=CROP_SETTINGS)
    # # user avatar thumb
    user_avatar_thumb = ThumbnailerImageField(
        null=True, blank=True,
        upload_to='Profiles/thumbs/%Y/%m/',
        verbose_name='User Avatar Thumb',
        resize_source=THUMB_CROP_SETTINGS)

    USERNAME_FIELD = settings.AUTH_USERNAME_FIELD
    REQUIRED_FIELDS = []

    objects = UserManager()

    def full_name(self):
        return str(self.first_name) + " " + str(self.last_name)

    def save(self, *args, **kwargs):
        self.username = self.email
        if self.pk:
            changed_fields = []
            cls = self.__class__
            old = cls.objects.get(pk=self.pk)
            new = self
            for field in cls._meta.get_fields():
                field_name = field.name
                try:
                    if getattr(old, field_name) != getattr(new, field_name):
                        changed_fields.append(field_name)
                except Exception as e:
                    print("exception:", e)
                    pass
            kwargs['update_fields'] = changed_fields
        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.email or self.username)


class UserLoginAttempt(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='user_login_attempts')
    is_failed = models.BooleanField(default=True)
    attempt_ip = models.CharField(max_length=30)

    def __str__(self):
        return str(self.user)


class GroupAndPermission(BaseModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              verbose_name=_('Group'),
                              related_name='group_permission')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE,
                                   verbose_name=_('Group Permission'),
                                   related_name='group_permission')
    company = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                verbose_name=_('Group Company'),
                                related_name='group_oganization')
    has_permission = models.BooleanField(verbose_name=_('Has Permission'),
                                         default=False)

    @classmethod
    def truncate(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                'TRUNCATE TABLE "{0}" CASCADE'.format(cls._meta.db_table))

    class Meta:
        unique_together = ["group", "permission", "company"]


from notifications.models import NotificationType


class Invitation(BaseModel):
    email = models.EmailField(unique=True,
                              verbose_name=_('E-mail Address'),
                              max_length=254)
    accepted = models.BooleanField(verbose_name=_('Accepted'),
                                   default=False)
    key = models.CharField(verbose_name=_('Key'),
                           max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('Invited By User'),
        null=True, blank=True, on_delete=models.CASCADE,
        related_name='invited_by_user')
    invited_by_company = models.ForeignKey(
        Organization, verbose_name=_('Invited By Company'),
        null=True, blank=False, on_delete=models.CASCADE,
        related_name='invited_by_company')
    invited_by_group = models.ForeignKey(
        Group, null=True, verbose_name=_('Invited As(Group)'),
        blank=True, on_delete=models.CASCADE,
        related_name='invited_by_group')
    email_notification = models.ManyToManyField(
        NotificationType,
        related_name='user_email_notification')
    in_app_notification = models.ManyToManyField(
        NotificationType,
        related_name='user_in_app_notification')
    title = models.CharField(max_length=254,
                             verbose_name=_('Title'), null=True,
                             blank=True)
    sent = models.DateTimeField(verbose_name=_('Sent'), null=True)
    is_owner = models.BooleanField(verbose_name=_('Is owner status'),
                                   default=False)
    first_name = models.CharField(max_length=254, null=True, blank=True,
                                  verbose_name=_('First Name'))
    last_name = models.CharField(max_length=254, null=True, blank=True,
                                 verbose_name=_('Last Name'))
    objects = BaseInvitationManager()

    @classmethod
    def create(cls, email, invited_by=None, **kwargs):
        key = str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
        instance = cls._default_manager.create(
            email=email,
            key=key,
            invited_by=invited_by,
            **kwargs)
        return instance

    def key_expired(self):
        expiration_date = (self.sent + datetime.timedelta(
            days=app_settings.INVITATION_EXPIRY))
        return expiration_date <= timezone.now()

    def send_invitation(self, request, **kwargs):
        # invite_url = reverse('authentication:accept-invite', args=[self.key])
        # invite_url = request.build_absolute_uri(invite_url)
        base_url = settings.SITE_URL.format(
            connection.schema_name).replace(':8080', '')
        invite_url = base_url + "/auth/signup/" + str(self.key)
        ctx = kwargs
        sender_name = request.user.first_name
        if not request.user.first_name:
            sender_name = "Admin"
        ctx.update({
            'invite_url': invite_url,
            'site_name': "PROXY by NMBL Technologies.",
            'email': self.email,
            'key': self.key,
            'invited_by': self.invited_by,
            'company': self.invited_by_company,
            'group': self.invited_by_group,
            'sender_name': sender_name,
        })
        email_template = 'invitations/email/email_invite'
        subject = "You are invited to Join PROXY by NMBL Technologies"
        from_email = '{} {} {} <{}>'.format(request.user.first_name,
                                            request.user.last_name,
                                            "[PROXY]",
                                            settings.DEFAULT_FROM_EMAIL)
        # when invited from super admin with no first name or last name
        if (not request.user.first_name) or (not request.user.last_name):
            from_email = settings.DEFAULT_FROM_EMAIL
        get_invitations_adapter().send_mail(email_template, self.email, ctx,
                                            subject, from_email)
        self.sent = timezone.now()
        self.save()
        signals.invite_url_sent.send(sender=self.__class__, instance=self,
                                     invite_url_sent=invite_url,
                                     invited_by=self.invited_by)

    def __str__(self):
        return "Invite: {0}".format(self.email)


class AddUser(Invitation):
    class Meta:
        proxy = True
        managed = False


# here for backwards compatibility, historic allauth adapter
if hasattr(settings, 'ACCOUNT_ADAPTER'):
    if settings.ACCOUNT_ADAPTER == 'authentication.models.InvitationsAdapter':
        from allauth.account.adapter import DefaultAccountAdapter
        from allauth.account.signals import user_signed_up


        class InvitationsAdapter(DefaultAccountAdapter):
            def is_open_for_signup(self, request):
                if hasattr(request, 'session') and request.session.get(
                        'account_verified_email'):
                    return True
                elif app_settings.INVITATION_ONLY is True:
                    # Site is ONLY open for invites
                    return False
                else:
                    # Site is open to signup
                    return True

            def get_user_signed_up_signal(self):
                return user_signed_up


class UserSetting(BaseModel):
    setting = models.CharField(max_length=254, db_index=True,
                               verbose_name=_('setting'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             verbose_name=_('User Setting'), null=True,
                             blank=True, on_delete=models.CASCADE,
                             related_name='user_setting')

    def __str__(self):
        return str(self.setting)


class CompanyInformation(BaseModel):
    company = models.ForeignKey(Organization, null=True,
                                verbose_name=_('Company Information'),
                                blank=True,
                                on_delete=models.CASCADE,
                                related_name='company_information')
    logo_url = models.CharField(null=True, blank=True, max_length=500)
    logo = models.FileField(upload_to='logo/', null=True, blank=True)
    background_color = models.CharField(null=True, blank=True,
                                        max_length=1000)
    message = models.TextField(null=True, blank=True, max_length=10000)
    font_color = models.CharField(null=True, blank=True, max_length=1000)

    def __str__(self):
        return str(self.company.name)


class IntroSlide(BaseModel):
    MODULE_TYPES = (
        ("project", "Project"),
        ("workflow", "Workflow"),
        ("task", "Task"),
        ("document", "Document"),
        ("group", "Group"),
        ("welcome", "Welcome")
    )
    title = models.CharField(max_length=100)
    message = models.TextField()
    image = models.ImageField(upload_to='introslideimage/',
                              blank=True, null=True)
    module = models.CharField(max_length=30, choices=MODULE_TYPES)
    rank = models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.rank == 0:
            self.rank = 1
        if self.id:
            old_rank = IntroSlide.objects.get(
                id=self.id).rank
            new_rank = self.rank
            if (new_rank < old_rank and new_rank):
                IntroSlide.objects.filter(
                    module=self.module,
                    rank__gte=new_rank, rank__lt=old_rank
                ).update(rank=F('rank') + 1)
            elif (new_rank > old_rank and new_rank):
                IntroSlide.objects.filter(
                    module=self.module,
                    rank__lte=new_rank, rank__gt=old_rank
                ).update(rank=F('rank') - 1)
        else:
            total_intro_slide = IntroSlide.objects.filter(
                module=self.module).count()
            new_rank = self.rank
            if new_rank:
                if new_rank >= total_intro_slide:
                    new_rank = total_intro_slide + 1
                else:
                    IntroSlide.objects.filter(
                        module=self.module,
                        rank__gte=new_rank).update(rank=F('rank') + 1)
            else:
                self.rank = total_intro_slide + 1

        super(IntroSlide, self).save(*args, **kwargs)


class UserIntroSlide(BaseModel):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    slide = models.ForeignKey('IntroSlide', on_delete=models.CASCADE)
    is_viewed = models.BooleanField(default=False)

    def __str__(self):
        return self.slide.title


# method for create user intro slide
@receiver(post_save, sender=User)
def create_intro_slide(sender, instance, created, **kwargs):
    if created and not (instance.is_staff or instance.is_superuser):
        qs = IntroSlide.objects.all()
        new_qs = [UserIntroSlide(slide=obj, user=instance) for obj in qs]
        UserIntroSlide.objects.bulk_create(new_qs)
