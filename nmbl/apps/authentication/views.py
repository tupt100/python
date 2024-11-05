import copy
import datetime
import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Case, When, Count, Q
from django.http import Http404
from django.shortcuts import redirect, HttpResponse, \
    HttpResponseRedirect, get_object_or_404
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, View, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django_filters.rest_framework import DjangoFilterBackend
from notifications.models import UserNotificationSetting, NotificationType
from projects.models import WorkGroupMember
from projects.serializers import ItemTitleRenameSerializer
from rest_framework import filters, mixins, status, viewsets
from rest_framework.authentication import TokenAuthentication, \
    SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, list_route
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from .adapters import get_invitations_adapter
from .app_settings import app_settings
from .exceptions import AlreadyAccepted, AlreadyInvited, \
    UserRegisteredEmail
from .filters import GroupFilterSet
from .forms import CleanEmailMixin, RegistrationForm, InviteForm
from .models import User, Invitation, UserLoginAttempt, \
    Permission, Group, GroupAndPermission, \
    PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES, DefaultPermission, \
    UserIntroSlide, CompanyInformation, Organization
from .permissions import PermissionManagerPermission, \
    BulkInvitePermission, CompanyInformationPermission, \
    CompanyUserPermission, UserPermission, GroupListPermission, \
    ListPendingInvitationPermission
from .serializers import (ShowUserSerializer, LoginAuthSerializer,
                          ShowPermissionSerializer, UserInviteSerializer,
                          ShowGroupSerializer, RegisterSerializer,
                          ResetPasswordSerializer, MyPermissionSerializer,
                          OrganizationGroupCreateSerializer,
                          UpdateUserSerializer, ChangePasswordSerializer,
                          InvitationUpdateSerializer, InvitationListSerializer,
                          UserAvatarUploadSerializer,
                          PermissionManagerListSerializer,
                          PermissionManagerUpdateSerializer,
                          CompanyInformationSerializer,
                          UserListSerializer,
                          GroupListSerializer, UserDetailUpdateSerializer,
                          UserDetailSerializer, GroupDetailSerializer,
                          InvitationDetailSerializer,
                          UserIntroSlideSerializer)
from .signals import invite_accepted
from .utils import get_client_ip, notify_company_owner, \
    invitation_send, user_group_change_notification


class HomeView(TemplateView):
    template_name = 'deshboard.html'


class SignUpView(FormView):
    form_class = RegistrationForm
    template_name = 'registration/signup.html'

    def form_valid(self, form):
        user = form.save(False)
        user.set_password(form.cleaned_data.get('password1'))
        user.is_active = True
        user.username = user.email
        user.key = get_random_string(64).lower()
        user.save()
        user = authenticate(username=user.email,
                            password=form.data['password1'])
        login(self.request, user)
        return HttpResponseRedirect(reverse('authentication:home'))


class SendInvite(FormView):
    template_name = 'invitations/forms/_invite.html'
    form_class = InviteForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(SendInvite, self).dispatch(
            request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        try:
            invite = form.save(email)
            invite.invited_by = self.request.user
            invite.save()
            invite.send_invitation(self.request)
        except Exception:
            return self.form_invalid(form)
        return self.render_to_response(
            self.get_context_data(
                success_message=_('%(email)s has been invited') % {
                    "email": email}))

    def form_invalid(self, form):
        return self.render_to_response(
            self.get_context_data(form=form))


class SendJSONInvite(View):
    http_method_names = [u'post']

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if app_settings.ALLOW_JSON_INVITES:
            return super(SendJSONInvite, self).dispatch(
                request, *args, **kwargs)
        else:
            raise Http404

    def post(self, request, *args, **kwargs):
        status_code = 400
        invitees = json.loads(request.body.decode())
        response = {'valid': [], 'invalid': []}
        if isinstance(invitees, list):
            for invitee in invitees:
                try:
                    validate_email(invitee)
                    CleanEmailMixin().validate_invitation(invitee)
                    invite = Invitation.create(invitee)
                except(ValueError, KeyError):
                    pass
                except(ValidationError):
                    response['invalid'].append({
                        invitee: 'invalid email'})
                except(AlreadyAccepted):
                    response['invalid'].append({
                        invitee: 'already accepted'})
                except(AlreadyInvited):
                    response['invalid'].append(
                        {invitee: 'pending invite'})
                except(UserRegisteredEmail):
                    response['invalid'].append(
                        {invitee: 'user registered email'})
                else:
                    invite.send_invitation(request)
                    response['valid'].append({invitee: 'invited'})

        if response['valid']:
            status_code = 201
        return HttpResponse(
            json.dumps(response),
            status=status_code, content_type='application/json')


class AcceptInvite(SingleObjectMixin, View):
    form_class = InviteForm

    def get_signup_redirect(self):
        return app_settings.SIGNUP_REDIRECT

    def get(self, *args, **kwargs):
        if app_settings.CONFIRM_INVITE_ON_GET:
            return self.post(*args, **kwargs)
        else:
            raise Http404()

    def post(self, *args, **kwargs):
        self.object = invitation = self.get_object()
        # Compatibility with older versions: return an HTTP 410 GONE if there
        # is an error. # Error conditions are: no key, expired key or
        # previously accepted key.
        if app_settings.GONE_ON_ACCEPT_ERROR and (not invitation or (
                invitation and (
                invitation.accepted or invitation.key_expired()))):
            return HttpResponse(status=410)

        # No invitation was found.
        if not invitation:
            # Newer behavior: show an error message and redirect.
            get_invitations_adapter().add_message(
                self.request, messages.ERROR,
                'invitations/messages/invite_invalid.txt')
            return redirect(app_settings.LOGIN_REDIRECT)

        # The invitation was previously accepted, redirect to the login
        # view.
        if invitation.accepted:
            get_invitations_adapter().add_message(
                self.request, messages.ERROR,
                'invitations/messages/invite_already_accepted.txt',
                {'email': invitation.email})
            # Redirect to login since there's hopefully an account already.
            return redirect(app_settings.LOGIN_REDIRECT)

        # The key was expired.
        if invitation.key_expired():
            get_invitations_adapter().add_message(
                self.request, messages.ERROR,
                'invitations/messages/invite_expired.txt',
                {'email': invitation.email})
            # Redirect to sign-up since they might be able to register anyway.
            return redirect(self.get_signup_redirect())

        # The invitation is valid.
        # Mark it as accepted now if ACCEPT_INVITE_AFTER_SIGNUP is False.
        if not app_settings.ACCEPT_INVITE_AFTER_SIGNUP:
            accept_invitation(invitation=invitation, request=self.request,
                              signal_sender=self.__class__)

        get_invitations_adapter().stash_verified_email(
            self.request, invitation.email)

        return redirect(self.get_signup_redirect())

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        try:
            return queryset.get(key=self.kwargs["key"].lower())
        except Invitation.DoesNotExist:
            return None

    def get_queryset(self):
        return Invitation.objects.all()


def accept_invitation(invitation, request, signal_sender):
    invitation.accepted = True
    invitation.save()

    invite_accepted.send(sender=signal_sender, email=invitation.email)

    get_invitations_adapter().add_message(
        request, messages.SUCCESS,
        'invitations/messages/invite_accepted.txt',
        {'email': invitation.email})


def accept_invite_after_signup(sender, request, user, **kwargs):
    invitation = Invitation.objects.filter(email=user.email).first()
    if invitation:
        accept_invitation(invitation=invitation, request=request,
                          signal_sender=Invitation)


if app_settings.ACCEPT_INVITE_AFTER_SIGNUP:
    signed_up_signal = get_invitations_adapter().get_user_signed_up_signal()
    signed_up_signal.connect(accept_invite_after_signup)


@csrf_exempt
def send_reinvite(request):
    email = request.POST.get('email_to_reinvite')
    invite = Invitation.objects.get(email=email)
    print(invite)
    invite.send_invitation(request)
    messages.add_message(request, messages.INFO,
                         "Re-Invite Link Sent Successfully!")
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


class SendResetPasswordAPIView(APIView):
    """
        Method  : POST
        url     : api/send-password-reset/<email>/
        Response: Status code 200 if mail sent successfully else
                    returns status code 400
        ----------
        If mail sent successfully
        Success Response Code :
        ----------
            200

        Error Response Code :
        ----------
            400

    """
    permission_classes = (AllowAny,)

    def post(self, request, email):
        # Accepts ID
        # Check if request is came from super admin
        if email:
            try:
                email = email.lower().strip()
                user_obj = User.objects.get(email=email)
                user_obj.key = \
                    str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                user_obj.save()
                from django.db import connection
                base_url = settings.SITE_URL.format(
                    connection.schema_name).replace(':8080', '')
                reset_link = base_url + "/auth/new-password/" + str(
                    user_obj.key)
                site = "PROXY by NMBL Technologies."
                ctx = {
                    "email": email,
                    "site_name": site,
                    'reset_link': reset_link,
                }
                subject = "We get it. Password are hard, We forget " \
                          "ours sometimes too. Wait.. " \
                          "no we don't. Forget we said that"
                message = get_template(
                    'password_reset/password_reset_message.html'
                ).render(ctx)
                msg = EmailMessage(subject, message, to=(email,),
                                   from_email='{} <{}>'.format(
                                       "PROXY SYSTEM",
                                       settings.DEFAULT_FROM_EMAIL))
                msg.content_subtype = 'html'
                msg.send()
                content = {
                    "detail": "Password Reset mail sent successfully!",
                    "status": 200,
                }
                return Response(content, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                content = {
                    "detail": "We're unable to find an "
                              "account that matches that"
                              " email address. Please try again.",
                    "status": 400,
                }
            return Response(content, status=status.HTTP_400_BAD_REQUEST)


class ActivateResetPasswordAPIView(GenericAPIView):
    """
        Method  : GET
        url     : api/resetpassword/<token>/
        Response: Status code 201, If password
                  changed successfully, else status code 400

        Method         : POST
        POST parameter : token, password, confirm_password
        Response       :

        ----------
        password changed successfully
        Success Response Code :
        ----------
            201

        Error Response Code :
        ----------
            400

    """
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordSerializer

    def get(self, request, token):
        try:
            # Get Token from user model
            is_token_present = User.objects.filter(key=token)
            if is_token_present:
                content = {
                    "detail": "Token is valid. Send a post request with "
                              "password and confirm_password fields"}
                return Response(content, status=status.HTTP_201_CREATED)
            else:
                content = {"detail": "Token is invalid or not found"}
                return Response(content, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("exception:", e)
            content = {"detail": "Token is invalid."}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, token):
        try:
            '''###Validations :
                1) check if token is not empty
                2) check if token exists in user model
                3) check if two provided passwords are same
            '''
            user = User.objects.get(key=token)
            serializer = self.serializer_class(user, data=request.data)
            if serializer.is_valid():
                user.set_password(request.data['password'])
                user.key = \
                    str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                user.save()
                return Response({"detail": "Password Changed Successfully!"},
                                status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "detail": "password or confirm_password is "
                              "null or did not match !."},
                    status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("exception:", e)
            content = {"detail": "Token has been "
                                 "expired or invalid token."}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)


class NewCompanySignUpAPIView(GenericAPIView):
    """
        Method  : GET
        url     : api/member-signup/<token>
        Response: prepopulated_values(
                    invited_by, invited_by_company,
                    invited_by_group) needed for signup

        Method         : POST
        POST parameter : invited_by, invited_by_company,
                         invited_by_group,email,password,
                         owner_name,owner_email
        Response       : Status code 200,
                          If User signup successfully,
                          else status code 400

        ----------
        If User signup successfully
        Success Response Code :
        ----------
            200

        Error Response Code :
        ----------
            400
    """
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def get(self, request, token):
        try:
            get_invitation_obj = Invitation.objects.get(key=token)
            get_invitation_obj.accepted = True
            get_invitation_obj.save()
            content = {"detail": "Invitation accepted !"}
            return Response(content, status=status.HTTP_201_CREATED)
        except Exception as e:
            content = {"detail": str(e)}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, token):
        """
        # Create Company here
        # Get invited_by, invited_by_company,
            invited_by_group from Front-end
        # From front end- we will get
            Group Name,company name,email,password
            and invited by email
        """
        try:
            get_invitation_obj = Invitation.objects.get(key=token)
            if get_invitation_obj.key_expired():
                content = {"detail": "Token has been expired !"}
                return Response(content, status=status.HTTP_400_BAD_REQUEST)
            get_invitation_obj.accepted = True
            get_invitation_obj.save()
            invited_by_group = get_invitation_obj.invited_by_group.name
        except Exception as e:
            print('exception:', e)
            content = {"detail": "Invalid token supplied !"}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_email = get_invitation_obj.email.lower().strip()
            user = User.objects.get(email__iexact=user_email)
            if user.is_delete:
                user.is_delete = False
                user.is_active = True
                user.save()
                # create user notification settings for the user
                # email-notification settings
                for custom_email_notification in \
                        get_invitation_obj.email_notification.all():
                    UserNotificationSetting.objects.create(
                        in_app_notification=False,
                        email_notification=True,
                        user=user,
                        notification_type=custom_email_notification)
                # in-app notifications
                for custom_in_app_notification in \
                        get_invitation_obj.in_app_notification.all():
                    UserNotificationSetting.objects.create(
                        in_app_notification=True,
                        email_notification=False,
                        user=user,
                        notification_type=custom_in_app_notification)
                detail = 'You have successfully signed up ' \
                         'as a Team Member !'
                if get_invitation_obj.is_owner:
                    detail = 'You have successfully ' \
                             'signed up as a Company User !'
                return Response({'token': str(user.auth_token),
                                 'detail': detail}, status.HTTP_201_CREATED)
            content = {"detail": "user with this email already exists."}
            return Response(content, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                user = User.objects.create_user(
                    first_name=serializer.validated_data['first_name'],
                    last_name=serializer.validated_data['last_name'],
                    password=serializer.validated_data['password'],
                    email=get_invitation_obj.email.lower().strip(),
                    username=get_invitation_obj.email.lower().strip(),
                    group=Group.objects.filter(
                        (Q(organization=get_invitation_obj.invited_by_company)
                         | Q(is_public=True))
                        & Q(name=invited_by_group)).first(),
                    company=get_invitation_obj.invited_by_company,
                    key=str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex)),
                    title=get_invitation_obj.title,
                    is_owner=get_invitation_obj.is_owner)
                if user.is_owner:
                    for notification_type in NotificationType.objects.all():
                        UserNotificationSetting.objects.create(
                            in_app_notification=True,
                            email_notification=True,
                            user=user,
                            notification_type=notification_type)
                # create user notification object
                for custom_email_notification in \
                        get_invitation_obj.email_notification.all():
                    UserNotificationSetting.objects.create(
                        in_app_notification=False,
                        email_notification=True,
                        user=user,
                        notification_type=custom_email_notification)
                for custom_in_app_notification in \
                        get_invitation_obj.in_app_notification.all():
                    UserNotificationSetting.objects.create(
                        in_app_notification=True,
                        email_notification=False,
                        user=user,
                        notification_type=custom_in_app_notification)
                detail = 'You have successfully signed ' \
                         'up as a Team Member !'
                if get_invitation_obj.is_owner:
                    detail = 'You have successfully signed ' \
                             'up as a Company User !'
                return Response({'token': str(user.auth_token),
                                 'detail': detail},
                                status.HTTP_201_CREATED)
            else:
                content = {"detail": serializer.errors}
                return Response(content,
                                status=status.HTTP_400_BAD_REQUEST)


class CompanyUserViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all user of my company
    ```
    * API to filter user's by group
    > filter user by groups pass group ids in "groups"
    e.g. : ?groups=1,2,3
    * To do Sorting on user by *first_name*,*last_name*,*title*
    > e.g : ascending by name > ordering=first_name
          descending by name > ordering=-first_name
    ```
    delete:
    API to delete user
    ```
    * To delete user pass user's id
    ```

    partial_update:
    API to update user's details
    ```
    * To update user's 'first_name',
      'last_name','group','title' pass id
       of that user with new data
    ```
    """
    permission_classes = (PermissionManagerPermission,
                          IsAuthenticated,
                          CompanyUserPermission,)
    http_method_names = ['get', 'delete', 'patch']
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ['first_name', 'last_name', 'title', ]

    def get_queryset(self):
        # only company owner and company admin can see all user's list
        group_list = []
        queryset = User.objects.none()
        groups = self.request.query_params.get('groups', '')
        if groups:
            [group_list.append(y) for y in groups.split(',')]
        user = self.request.user
        company = user.company
        if company:
            queryset = User.objects.filter(company=company,
                                           is_delete=False
                                           ).exclude(pk=user.pk)
            if groups:
                return queryset.filter(group__in=group_list)
            else:
                return queryset
        return queryset

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return UpdateUserSerializer
        if self.action == 'retrieve':
            return UpdateUserSerializer
        return ShowUserSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        queryset = self.get_queryset()
        instance = get_object_or_404(queryset,
                                     pk=int(kwargs.get('pk')))
        if request.data.get('group') and \
                instance.group.id != request.data.get('group'):
            # restrict company admin to make any user to company admin
            if (request.data.get('group') == 5 and
                request.user.group.is_company_admin) \
                    or instance.group.id == 5:
                return Response(
                    {'detail': "You don't have permission "
                               "to perform this action"},
                    status=status.HTTP_403_FORBIDDEN)
        copy_instance_group = copy.copy(instance.group.name)
        # restrict company admin to make any changes on company owner's user
        if instance.is_owner and not request.user.is_owner:
            response = {
                "detail": "You don't have permission to perform this action"}
            return Response(response, status.HTTP_403_FORBIDDEN)
        ROLE_CHANGE = False
        if request.data.get('group') and \
                instance.group.id != request.data.get('group'):
            user_group_change_notification.delay(instance)
            ROLE_CHANGE = True
        serializer = self.get_serializer(instance, data=request.data,
                                         partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if ROLE_CHANGE:
            # send In-APP notification to company owner
            # when member's role gets change
            notify_company_owner(instance, copy_instance_group)
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset,
            # we need to forcibly invalidate the prefetch
            # cache on the instance.
            instance._prefetched_objects_cache = {}
        return Response({"detail": "User Updated Successfully!"})

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        company = user.company
        # do not allow user to delete company owner
        if (user.is_owner or user.group.is_company_admin
                and not request.user.is_owner):
            response = {
                "detail": "You don't have permission to perform this action"}
            return Response(response, status.HTTP_403_FORBIDDEN)
        user.is_delete = True
        user.is_active = False
        user.save()
        # delete user notification settings, groups for that user
        Invitation.objects.filter(email__iexact=user.email,
                                  invited_by_company=company
                                  ).delete()
        UserNotificationSetting.objects.filter(
            user=user, user__company=company).delete()
        WorkGroupMember.objects.filter(work_group__organization=company,
                                       group_member=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginAuthentication(ObtainAuthToken, GenericAPIView):
    """
        Method  : POST
        POST parameters: email, password
        Description : This APIView will log in user
        Response: id','username','first_name',
        'last_name','email','group','company'
    """
    permission_classes = (AllowAny,)
    serializer_class = LoginAuthSerializer

    def post(self, request, *args, **kwargs):
        def create_login_attempt(user, is_failed=True):
            ip = get_client_ip(request)
            UserLoginAttempt.objects.create(
                user=user, is_failed=is_failed, attempt_ip=ip)

        MAX_ATTEMPTS = 5
        ATTEMPTS_RESET_TIME = 24  # in hours
        try:
            user_check = User.objects.get(
                email__iexact=request.data['username'].lower().strip())
        except Exception as e:
            print('Error: ', e)
            response = {
                "detail": "We can't find that email "
                          "address in our records, please try again!"}
            return Response(response, status.HTTP_404_NOT_FOUND)
        date_from = datetime.datetime.now() - datetime.timedelta(
            hours=ATTEMPTS_RESET_TIME)
        failed_attempt_cnt = UserLoginAttempt.objects.filter(
            user=user_check, is_failed=True,
            created_at__gte=date_from).count()
        if failed_attempt_cnt >= MAX_ATTEMPTS:
            message = "You have reached the maximum {} incorrect login " \
                      "attempts. Please try after {} hours" \
                      "".format(MAX_ATTEMPTS, ATTEMPTS_RESET_TIME)
            response = {"detail": message}
            return Response(response, status.HTTP_400_BAD_REQUEST)
        password = request.data['password']
        user = authenticate(username=user_check.email,
                            password=password)
        if user and user.is_active:
            if not user.is_superuser:
                if user.is_authenticated:
                    login(request, user)
                    create_login_attempt(user, False)
                    token_obj, created = \
                        Token.objects.get_or_create(user=user)
                    return Response({'token': str(token_obj.key)},
                                    status.HTTP_200_OK)
                create_login_attempt(user_check)
                return Response({
                    "detail": "The password you entered is incorrect."},
                    status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Super User Can't Login from here."},
                            status.HTTP_400_BAD_REQUEST)
        create_login_attempt(user_check)
        return Response({
            "detail": "The password you entered is incorrect."},
            status.HTTP_400_BAD_REQUEST)


class LogoutAuthentication(APIView):
    """
        Method : GET
        Description : This APIView will logout the current user
    """
    permission_classes = (IsAuthenticated,)
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)

    def get(self, request):
        try:
            logout(request)
            return Response({"detail": "Logged Out Successfully!"},
                            status.HTTP_200_OK)
        except Exception as e:
            print("exception:", e)
            return Response({"detail": "Some Error Occurred"
                                       " While Logging Out"},
                            status.HTTP_401_UNAUTHORIZED)


class InviteMemberAPIView(GenericAPIView):
    """
    API for Company User To Send Invite Other Team Members

    API : api/invite-member/
    Response : Status Code 200 if mail sent else Status Code 400

    method : POST
    Params : email,invited_by_group,title
    """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)
    serializer_class = UserInviteSerializer

    def post(self, request):
        try:
            if request.data.get('invited_by_group') == 5 and \
                    self.request.user.group.is_company_admin:
                return Response(
                    {'detail': "You don't have permission "
                               "to perform this action"},
                    status=status.HTTP_403_FORBIDDEN)
            serializer_data = self.serializer_class(data=request.data)
            email = request.data.get('email').lower().strip()
            user = User.objects.filter(
                email=email, company=self.request.user.company,
                is_delete=True).last()
            if user:
                if serializer_data.is_valid():
                    # send re-invitation to user with notification settings
                    invite = serializer_data.save()
                    invite.email = user.email
                    invite.key = \
                        str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                    invite.invited_by_company = request.user.company
                    invite.invited_by = request.user
                    invite.sent = timezone.now()
                    # assign all in-app notifications type objects to invite
                    invite.in_app_notification.set(
                        NotificationType.objects.all())
                    #  assign all email notifications type objects to invite
                    invite.email_notification.set(
                        NotificationType.objects.all())
                    invite.save()
                    invitation_send.delay(request.user, invite)
                    content = {"detail": "Invite sent successfully"}
                    return Response(content, status=status.HTTP_200_OK)
            if serializer_data.is_valid():
                invite = serializer_data.save()
                invite.key = \
                    str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                invite.invited_by_company = request.user.company
                invite.invited_by = request.user
                invite.email = email
                # assign all in-app notifications type objects to invite
                invite.in_app_notification.set(
                    NotificationType.objects.all())
                #  assign all email notifications type objects to invite
                invite.email_notification.set(
                    NotificationType.objects.all())
                invite.sent = timezone.now()
                invite.save()
                invitation_send.delay(request.user, invite)
                content = {"detail": "Invite sent successfully!"}
                return Response(content, status=status.HTTP_200_OK)
            else:
                content = {"detail": "Invitation with this e-mail Address "
                                     "already exists!"}
                return Response(content,
                                status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            content = {"detail": str(e)}
            return Response(content, status.HTTP_400_BAD_REQUEST)


class PermissionAPIView(APIView):
    """
        Method  : GET
        url     : /api/permission/
        Response: List of all Permission
    """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)

    def get(self, request):
        paginator = PageNumberPagination()
        query_set = Permission.objects.all()
        context = paginator.paginate_queryset(query_set, request)
        serializer = ShowPermissionSerializer(context, many=True)
        return paginator.get_paginated_response(serializer.data)


class PermissionTypeWiseAPIView(APIView):
    """
        Method  : GET
        url     : /api/permission-types/
        Response: List of all Permission
                  type wise(projects, workflows and tasks)
    """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)

    def get(self, request):
        items = {}
        for key, value in PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES():
            items[f'{key}_permissions'] = Permission.objects.filter(
                permission_category=key).order_by('pk').values('id', 'name', 'slug')
        return Response(
            items,
            status=status.HTTP_200_OK)


class GroupAPIView(APIView):
    """
        Method  : GET
        url     : /api/group/
        Response: List of all Groups
    """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)
    authentication_classes = (TokenAuthentication,
                              SessionAuthentication)

    def get(self, request):
        try:
            queryset = Group.objects.filter(
                Q(organization=request.user.company) | Q(is_public=True)
            ).annotate(
                public_group=Case(When(
                    is_public=True, then=('id')), default=None
                ),
                organization_group=Case(When(
                    is_public=False, then=('name')),
                    default=None)
            ).order_by('public_group', 'organization_group', )
            serializer = ShowGroupSerializer(queryset, many=True)
            # customize response for list of
            # permission attached with the company's group
            # add permissions
            response = []
            for group_obj in serializer.data:
                temp_dict = {}
                # for project permissions
                permissions_p = []
                p_permissions = GroupAndPermission.objects.filter(
                    group_id=group_obj['id'],
                    company=request.user.company,
                    has_permission=True,
                    permission_id__slug__startswith="project"
                ).order_by('pk')
                for p in p_permissions:
                    p_permission_serializer = ShowPermissionSerializer(
                        p.permission)
                    permissions_p.append(p_permission_serializer.data)
                # for workflow permissions
                permissions_w = []
                w_permissions = GroupAndPermission.objects.filter(
                    group_id=group_obj['id'],
                    company=request.user.company,
                    has_permission=True,
                    permission_id__slug__startswith="workflow"
                ).order_by('pk')
                for w in w_permissions:
                    w_permission_serializer = ShowPermissionSerializer(
                        w.permission)
                    permissions_w.append(w_permission_serializer.data)
                # for task permissions
                permissions_t = []
                t_permissions = GroupAndPermission.objects.filter(
                    group_id=group_obj['id'],
                    company=request.user.company,
                    has_permission=True,
                    permission_id__slug__startswith="task"
                ).order_by('pk')
                for t in t_permissions:
                    t_permission_serializer = ShowPermissionSerializer(
                        t.permission)
                    permissions_t.append(t_permission_serializer.data)
                # for request permission
                permissions_r = []
                r_permissions = GroupAndPermission.objects.filter(
                    group_id=group_obj['id'],
                    company=request.user.company,
                    has_permission=True,
                    permission_id__slug__startswith="request"
                ).order_by('pk')
                for r in r_permissions:
                    r_permission_serializer = ShowPermissionSerializer(
                        r.permission)
                    permissions_r.append(r_permission_serializer.data)
                temp_dict = {
                    'id': group_obj['id'],
                    'name': group_obj['name'],
                    'is_user_specific': group_obj['is_user_specific'],
                    'is_public': group_obj['is_public'],
                    'project_permissions': permissions_p,
                    'workflow_permissions': permissions_w,
                    'task_permissions': permissions_t,
                    'request_permissions': permissions_r
                }
                response.append(temp_dict)
            return Response({'results': response}, status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status.HTTP_400_BAD_REQUEST)


class ListPendingInvitationViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all user who have not accept in invitation

    * API to get list of all user who have not accept in invitation
    ```
    To sort groups
    > Sorting fields: 'first_name', 'last_name','title'
      e.g : ascending by name > ordering=first_name
         descending by name > ordering=-first_name
    > filter user by groups pass group ids in "groups"
      e.g. : ?groups=1,2,3
    ```

    partial_update:
    API to update member's group or title

    * API to update member's group or title who have not accept in invitation
    ```
     > 'invited_by_group' would be group id
        ex:'invited_by_group': 1
    ```
    """
    permission_classes = (PermissionManagerPermission,
                          ListPendingInvitationPermission,
                          IsAuthenticated,)
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ['first_name', 'last_name', 'title', ]
    http_method_names = ['get', 'delete', 'patch']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        group_list = []
        groups = self.request.query_params.get('groups', '')
        queryset = Invitation.objects.none()
        if company:
            queryset = Invitation.objects.filter(
                invited_by_company=company, accepted=False)
            if groups:
                [group_list.append(y) for y in groups.split(',')]
                return queryset.filter(invited_by_group__in=group_list)
        return queryset

    def get_serializer_class(self):
        return InvitationUpdateSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = Invitation.objects.get(
            pk=int(kwargs.get('pk')),
            accepted=False,
            invited_by_company=request.user.company)
        if (request.data.get('invited_by_group') == 5 or
            instance.invited_by_group.is_company_admin) \
                and not request.user.is_owner:
            return Response(
                {'detail': "You don't have permission to "
                           "perform this action"},
                status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance, data=request.data,
                                         partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to
            # a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        response = {"detail": "Invitation Updated Successfully!"}
        return Response(response, status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = InvitationListSerializer(
            context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class MyPermissionAPIView(mixins.ListModelMixin, GenericViewSet):
    """
    list:
    API to get list of permission i have
    ```
    * API To get all my Permissions
    > model_type options task, project, workflow, request, tasktemplate
    e.g.: to Filter by task pass "model_type"="task"
    ```
    """
    queryset = GroupAndPermission.objects.all()

    def get_queryset(self):
        model_type = self.request.GET.get('model_type')
        user = self.request.user
        q_obj = Q(company=user.company, group=user.group)
        q_obj.add(Q(has_permission=True), Q.AND)
        model_choices = list(
            map(lambda x: x[0].lower(), PERMISSION_TENANT_ALLOW_CATEGORY_CHOICES()))
        if model_type and model_type.lower() in model_choices:
            q_obj.add(Q(permission__permission_category=model_type), Q.AND)
        queryset = GroupAndPermission.objects.filter(q_obj)
        return queryset

    def get_serializer_class(self):
        return MyPermissionSerializer


class OrganizationGroupViewSet(viewsets.ModelViewSet):
    """
    create:
    API to create new group

    * API to create bew group
    ```
    > To create new group pass group name and
       permission ids in "default_permissions"
    ```
    """
    permission_classes = (PermissionManagerPermission,
                          IsAuthenticated,)
    serializer_class = OrganizationGroupCreateSerializer
    queryset = Group.objects.all()
    http_method_names = ['post', 'get', 'patch']

    def get_queryset(self):
        and_filter = {}
        q_filter = Q()
        if not self.request.user.is_superuser:
            and_filter['organization'] = self.request.user.company
            if self.request.user.company and \
                    self.request.user.is_owner is True:
                self.queryset = self.queryset.exclude(status='inactive')
        return self.queryset.filter(
            **and_filter
        ).filter(q_filter)

    def create(self, request, *args, **kwargs):
        # condition to check if is_public is passed in
        # the data & pop it out
        # from the request data before passing to serializer.
        company = request.user.company
        is_public = request.data.get('is_public', False)
        if is_public:
            request.data.pop("is_public")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # attach permissions as per the Through Table
        group_obj = Group.objects.get(id=serializer.data['id'])
        permission_objs = Permission.objects.filter(
            id__in=self.request.data.get('default_permissions', None))
        for permission_data in permission_objs:
            DefaultPermission.objects.create(
                group=group_obj,
                permission=permission_data,
                has_permission=True)
            GroupAndPermission.objects.create(
                group=group_obj,
                permission=permission_data,
                company=company,
                has_permission=True)
        response = serializer.data
        return Response(
            response,
            status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        group_obj = self.get_object()
        if group_obj:
            if group_obj.organization_id == request.user.company.id and \
                    ('default_permissions' in request.data.keys()):
                # remove exist permission
                DefaultPermission.objects.filter(
                    group=group_obj
                ).delete()
                GroupAndPermission.objects.filter(
                    group=group_obj
                ).delete()
                # create and attached new permissions to group
                permission_objs = Permission.objects.filter(
                    id__in=request.data.get('default_permissions', None))
                for permission_data in permission_objs:
                    DefaultPermission.objects.create(
                        group=group_obj,
                        permission=permission_data,
                        has_permission=True
                    )
                    GroupAndPermission.objects.create(
                        group=group_obj,
                        permission=permission_data,
                        company=request.user.company,
                        has_permission=True
                    )
                return Response(
                    {"detail": "User Role is updated "
                               "with new permissions."},
                    status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"detail": "Oops, Sorry! Group is "
                               "not exist in your company."},
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(
                {"detail": "Oops, Sorry! Group is not exist."},
                status=status.HTTP_400_BAD_REQUEST
            )


class PermissionManagerViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list of all groups (except 'user_specific')
    # following details can be get from this API
    # count of total user who has that group assigned
    # total project/task/workflow permission vs
        project/task/workflow that group has
    # group which has *can_be_delete* can not be deleted

    ```
    * API to sorting groups by name
    > e.g : ascending by name > ?ordering=name
          descending by name > ordering=-name
    ```

    group_delete:
    * API to delete group
    ```
    * To delete pass group id
    > if group is assign to any user then pass user
       id and new group as below
    * {"users_updated_roles":[{"user":{user_id},"role":{group_id}]}
    ```

    partial_update:
    API to update group's permission
    ```
    * To update permission pass all permission id's
       in "default_permissions"
    e.e.: "default_permissions: [16, 17, 18, 19, 21]
    ```
    """
    permission_classes = (PermissionManagerPermission,)
    ordering_filter = filters.OrderingFilter()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = GroupFilterSet
    http_method_names = ['patch', 'post', 'get', 'delete']

    serializers = {
        'list': PermissionManagerListSerializer,
        'partial_update': PermissionManagerUpdateSerializer,
        'group_rename': ItemTitleRenameSerializer
    }

    def get_queryset(self):
        queryset = Group.objects.filter(
            Q(organization=self.request.user.company) | Q(is_public=True)
        ).exclude(is_user_specific=True).annotate(
            public_group=Case(When(
                is_public=True, then=('id')), default=None),
            organization_group=Case(When(
                is_public=False, then=('name')), default=None),
            users_count=Count(
                'user_group',
                filter=Q(user_group__company=self.request.user.company,
                         user_group__is_delete=False))
        ).order_by('public_group', 'organization_group', )
        return queryset

    def filter_queryset(self, queryset):
        queryset = super(PermissionManagerViewSet,
                         self).filter_queryset(queryset)
        return self.ordering_filter.filter_queryset(self.request,
                                                    queryset, self)

    def get_serializer_class(self):
        tg_serializer_class = self.serializers.get(self.action)
        if tg_serializer_class is None:
            return PermissionManagerListSerializer
        return tg_serializer_class

    def list(self, request):
        # List all the groups and necessary information
        # in permission manager
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    def partial_update(self, request, pk=None):
        # Update permissions for custom created user role.
        if not request.data.get("default_permissions"):
            return Response({"detail": "default_permissions "
                                       "is a required field."},
                            status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset()
        group_obj = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer(group_obj,
                                         data=request.data,
                                         partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response({"detail": ("User Role is updated "
                                        "with new permissions")},
                            status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch', ])
    def group_delete(self, request, pk=None):
        queryset = self.get_queryset()
        group_instance = get_object_or_404(queryset, pk=pk)
        company = request.user.company
        users_updated_roles = \
            request.data.get("users_updated_roles", [])
        # check if the user is trying to delete admin's
        # role or company owner's role.
        if group_instance.is_company_admin or \
                not group_instance.can_be_delete:
            return Response({"detail": "You cannot delete "
                                       "a admin roles."},
                            status=status.HTTP_400_BAD_REQUEST)
        # users count for the Role
        users_count = group_instance.user_group.all().filter(
            company=request.user.company,
            is_delete=False).count()
        # Check if the user is trying to delete a
        # customer Role with users
        # assigned to it.
        if users_count != len(users_updated_roles):
            return Response({"detail": ("You cannot delete a role without "
                                        "reassigning active users "
                                        "of the group")},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                for user_and_group in users_updated_roles:
                    user_obj = User.objects.get(
                        id=user_and_group.get("user"), company=company)
                    group_obj = Group.objects.get(
                        id=user_and_group.get("role"))
                    if group_obj == group_instance:
                        return Response({"detail": "Cannot assign "
                                                   "deleting role to user."},
                                        status=status.HTTP_400_BAD_REQUEST)
                    user_obj.group = group_obj
                    user_obj.save()
                    user_group_change_notification.delay(user_obj)
                    notify_company_owner(user_obj, group_instance.name)
                group_instance.delete()
        except ObjectDoesNotExist:
            return Response({"detail": "Either user or "
                                       "Role passed, doesnt exist."},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Role removed Successfully."},
                        status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch', ])
    def group_rename(self, request, pk=None):
        """
        Extra action to rename/update title of a Group.

        * to rename group name Group-Id need to be passed.

        ```
        To update/rename title pass `name` as below:
        { "name": "updating task title" }
        ```
        """
        queryset = self.get_queryset()
        instance = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            instance.name = serializer.data['name']
            instance.save()
            return Response({'detail': 'Group name updated successfully.'},
                            status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = get_object_or_404(self.get_queryset(),
                                     pk=int(kwargs.get('pk')))
        company = instance.organization
        admin_role = User.objects.get(
            is_owner=True, company=company).group
        # do not allow user to delete admin roles
        if instance.is_company_admin or \
                instance == admin_role or not instance.can_be_delete:
            response = {
                "detail": "You can not delete admin roles"}
            return Response(response, status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(
                company=company, group=instance,
                is_delete=False).exists():
            response = {
                "detail": "You cannot delete a role without "
                          "reassigning active users of the group"}
            return Response(response, status.HTTP_400_BAD_REQUEST)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResendInvitationAPIView(APIView):
    """
        API to send re-invite user who have not accepted invitation
        Method  : POST
        url     : api/resend-pending-invite/<id>/
    """
    permission_classes = (IsAuthenticated,
                          PermissionManagerPermission,)

    def post(self, request, id):
        try:
            invite_obj = Invitation.objects.get(
                id=id,
                invited_by_company=request.user.company,
                accepted=False)
            invitation_send.delay(request.user, invite_obj)
            invite_obj.sent = timezone.now()
            invite_obj.save()
            content = {"detail": "Invite sent successfully."}
            return Response(content, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({"detail": "Invitation for this user "
                                       "does not exist."},
                            status=status.HTTP_400_BAD_REQUEST)


class BulkInvitationView(viewsets.GenericViewSet):
    permission_classes = (PermissionManagerPermission,
                          BulkInvitePermission,)
    serializer_class = UserInviteSerializer

    @list_route(methods=['POST'])
    def send_bulk_invitation(self, request):
        """
        * API to send bulk invitation
        '''
        {
        "data": [
                {
                  "email": "srakholiya+1@codal.com",
                  "invited_by_group": "5",
                  "title": "codalite1",
                  "first_name":"codal",
                  "last_name":"codal",
                },
                {
                  "email": "srakholiya+2@codal.com",
                  "invited_by_group": "2",
                  "title": "codalite2",
                   "first_name":"codal",
                  "last_name":"codal",
                }
                ]
        }
        ```
        """
        invalid_data = {'invalid_invitation': [],
                        'valid_invitation': []}
        for invitation_data in request.data.get('data'):
            invitation = UserInviteSerializer(data=invitation_data)
            invite_email = invitation_data.get('email').lower().strip()
            # check if user with the same email already exists
            # and have not accepted invitation
            already_invited = Invitation.objects.filter(
                email__iexact=invite_email,
                invited_by_company=request.user.company,
                accepted=False).last()
            # check if user was deleted in same company
            deleted_user = User.objects.filter(
                email__iexact=invite_email,
                company=request.user.company,
                is_delete=True).last()
            if already_invited:
                # if exist then send re-invitation
                invitation_send.delay(request.user, already_invited)
                already_invited.sent = timezone.now()
                already_invited.save()
                invalid_data['valid_invitation'].append(invite_email)
            # check if user already exist or invited
            # before and accepted invitation
            elif Invitation.objects.filter(
                    email__iexact=invite_email,
                    invited_by_company=request.user.company,
                    accepted=True).exists() or \
                    User.objects.filter(email=invite_email,
                                        company=request.user.company,
                                        is_delete=False).exists():
                invalid_data['invalid_invitation'].append(invite_email)
                pass
            elif deleted_user:
                if invitation.is_valid():
                    # deleted user notification settings for that user
                    Invitation.objects.filter(
                        email__iexact=deleted_user.email,
                        invited_by_company=request.user.company
                    ).delete()
                    UserNotificationSetting.objects.filter(
                        user=deleted_user).delete()
                    # send re-invitation to user with notification settings
                    invite = invitation.save()
                    invite.email = invite_email
                    invite.key = \
                        str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                    invite.invited_by_company = request.user.company
                    invite.invited_by = request.user
                    invite.sent = timezone.now()
                    # assign all in-app notifications type objects to invite
                    invite.in_app_notification.set(
                        NotificationType.objects.all())
                    #  assign all email notifications type objects to invite
                    invite.email_notification.set(
                        NotificationType.objects.all())
                    invite.save()
                    invitation_send.delay(request.user, invite)
                    invalid_data['valid_invitation'].append(invite_email)
                else:
                    invalid_data['invalid_invitation'].append(invite_email)
            else:
                if invitation.is_valid():
                    # send invitation
                    invite = invitation.save()
                    invite.email = invite_email
                    invite.key = \
                        str(uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid4().hex))
                    invite.invited_by_company = request.user.company
                    invite.invited_by = request.user
                    invite.sent = timezone.now()
                    # assign all in-app notifications type objects to invite
                    invite.in_app_notification.set(
                        NotificationType.objects.all())
                    #  assign all email notificactions type objects to invite
                    invite.email_notification.set(
                        NotificationType.objects.all())
                    invite.save()
                    invitation_send.delay(request.user, invite)
                    invalid_data['valid_invitation'].append(invite_email)
                else:
                    invalid_data['invalid_invitation'].append(invite_email)
        response = invalid_data
        response['detail'] = "Invite sent successfully"
        return Response(response, status=status.HTTP_200_OK)


class CompanyInformationViewSet(viewsets.ModelViewSet):
    permission_classes = (AllowAny, CompanyInformationPermission,)

    def get_queryset(self):
        return CompanyInformation.objects.filter(
            company=Organization.objects.first())

    def get_serializer_class(self):
        return CompanyInformationSerializer


class UserListViewSet(ListModelMixin, viewsets.GenericViewSet):
    """
    list:
    API to list all users

    * API to get list of my company users
    ```
    To sort groups
    Sorting fields: 'first_name','last_name',
    e.g : ascending by first_name > ordering=first_name
         descending by first_name > ordering=-first_name
    To search user pass user name
        e.g.: ?search=codal
    ```
    """
    permission_classes = (CompanyInformationPermission,
                          IsAuthenticated,)
    filter_backends = (filters.SearchFilter,)
    ordering_fields = ['first_name', 'last_name', ]
    search_fields = ['first_name', 'last_name']
    http_method_names = ['get']

    def get_queryset(self):
        user = self.request.user
        company = user.company
        if company:
            queryset = User.objects.filter(
                company=company, is_delete=False)
            return queryset
        return User.objects.none()

    def get_serializer_class(self):
        return UserListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = UserListSerializer(
            context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class GroupListViewSet(viewsets.ModelViewSet):
    """
    list:
    API to list all roles/groups

    * API to get list of all roles/groups
    ```
    To sort groups
    Sorting fields: 'name',
    e.g : ascending by name > ordering=name
         descending by name > ordering=-name
    To search user pass group name
    e.g.: ?search=codal
    ```
    """
    permission_classes = (PermissionManagerPermission,
                          GroupListPermission,
                          IsAuthenticated,)
    filter_backends = (filters.SearchFilter,)
    ordering_fields = ['name', ]
    search_fields = ['name', ]
    http_method_names = ['get', ]

    def get_queryset(self):
        user = self.request.user
        company = user.company
        if company:
            queryset = Group.objects.filter(
                Q(organization=company) | Q(is_public=True)
            ).exclude(is_user_specific=True)
            return queryset
        return Group.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return GroupListSerializer
        else:
            return GroupDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        context = self.paginate_queryset(queryset)
        serializer = GroupListSerializer(
            context, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = (UserPermission, IsAuthenticated,)

    def get_queryset(self):
        queryset = User.objects.none()
        user = self.request.user
        email = user.email.lower().strip()
        company = user.company
        if company:
            queryset = User.objects.filter(
                email__iexact=email, company=company,
                is_delete=False)
            return queryset
        return queryset

    def get_serializer_class(self):
        if self.action == 'change_password':
            return ChangePasswordSerializer
        elif self.action == 'upload_avatar':
            return UserAvatarUploadSerializer
        else:
            return UserDetailUpdateSerializer

    @action(detail=False, methods=['patch', ])
    def change_password(self, request, pk=None):
        """
        * To change password enter
        ```
        > pass 'current_password' and 'new_password'
        ```
        """
        user = request.user
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.is_valid():
            if not user.check_password(
                    serializer.validated_data.get('current_password')):
                return Response(
                    {
                        'detail': 'Your Current password was '
                                  'incorrect, please try again!'},
                    status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data.get('new_password'))
            user.save()
            return Response(
                {'detail': 'Password changed successfully'},
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get', ])
    def me(self, request, pk=None):
        user = request.user
        return Response(
            UserDetailSerializer(user, context={"request": request}).data)

    @action(detail=False, methods=['patch', 'delete'])
    def upload_avatar(self, request):
        """
        Extra actions to upload/remove user Avatar.
        patch:
        API to upload user avatar

        * to upload a user avatar authorization token needs to be passed.
        ```
        To upload/update avatar pass `user_avatar` as below:
        { "name": "Base64String" } `or`
        { "name": "<ImageFile>" }
        ```

        delete:
        API to remove user avatar.

        * To remove existing avatar, authorization token needs to be passed.
        ```
        To upload/update avatar, no need to send any key. Just call the API.
        ```
        """
        user_instance = request.user
        if request.method == 'PATCH':
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                # delete previous existing avatar
                user_instance.user_avatar.delete()
                # update with new avatar
                user_instance.user_avatar = serializer. \
                    validated_data['user_avatar']
                # update user avatar thumb
                user_instance.user_avatar_thumb = serializer. \
                    validated_data['user_avatar']
                # save user instance
                user_instance.save()
                return Response({'detail': 'user avatar updated.'},
                                status=status.HTTP_200_OK)
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        if request.method == 'DELETE':
            if self.request.data:
                return Response({
                    'detail': 'Extra arguments are passed in request.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if not user_instance.user_avatar:
                return Response({
                    'detail': 'User does not have an avatar.'},
                    status=status.HTTP_400_BAD_REQUEST)
            # delete user avatar and thumb files
            user_instance.user_avatar.delete()
            if user_instance.user_avatar_thumb:
                user_instance.user_avatar_thumb.delete()
            return Response({'detail': 'User Avatar Deleted.'},
                            status=status.HTTP_200_OK)


class InvitationVerificationAPIView(APIView):
    """
    * Invitation verification API
    ```
    API to Verify invitation
    > if token is valid then return email, first_name, last_name
    > if token is invalid then return 400
    ```
    """
    permission_classes = (AllowAny,)

    def get(self, request, token):
        try:
            invite_obj = Invitation.objects.get(key=token, accepted=False)
            response = InvitationDetailSerializer(invite_obj).data
            response["detail"] = "Valid token."
            return Response(response, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({"detail": "Invalid token."},
                            status=status.HTTP_400_BAD_REQUEST)


class UserIntroSlideAPIView(APIView):
    """
    * API will return Intro-Slide based on module
    ```
    API to Verify request
    > url parameter 'module' required
      otherwise it will return 404
    > module parameter value will be
      accept ('project', 'workflow', 'task', 'document',
      'group', 'welcome')
    ```
    """
    permission_classes = [IsAuthenticated]

    def get_object(self):
        acceptable_module_parm = ['project', 'workflow',
                                  'task', 'document',
                                  'group', 'welcome']
        user = self.request.user
        module = self.request.query_params.get('module')
        queryset = UserIntroSlide.objects.filter(user=user,
                                                 is_viewed=False)
        if module and module in acceptable_module_parm:
            queryset = queryset.filter(
                slide__module=self.request.query_params.get('module')
            ).order_by('slide__rank')
        else:
            raise Http404('Missing required parameters')
        return queryset

    def get(self, request, format=None):
        instance_introslide = self.get_object()
        if instance_introslide:
            is_introslide = True
        else:
            is_introslide = False
        serializer = UserIntroSlideSerializer(instance_introslide, many=True)
        return Response(
            {"is_introslide": is_introslide, "introslide": serializer.data},
            status=status.HTTP_200_OK)

    def patch(self, request, format=None):
        instance_introslide = self.get_object()
        instance_introslide.update(is_viewed=True)
        return Response(
            {"detail": "Intro-Slide updated successfully."},
            status=status.HTTP_200_OK)
