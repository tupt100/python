from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include
from rest_framework import routers
from rest_framework_swagger.views import get_swagger_view

from .views import CompanyUserViewSet, UserViewSet, \
    MyPermissionAPIView, OrganizationGroupViewSet, \
    PermissionManagerViewSet, BulkInvitationView, \
    CompanyInformationViewSet, UserListViewSet, GroupListViewSet, \
    ListPendingInvitationViewSet, SignUpView, \
    HomeView, SendInvite, SendJSONInvite, AcceptInvite, \
    send_reinvite, LoginAuthentication, LogoutAuthentication, \
    ActivateResetPasswordAPIView, SendResetPasswordAPIView, \
    NewCompanySignUpAPIView, InviteMemberAPIView, \
    PermissionAPIView, PermissionTypeWiseAPIView, \
    GroupAPIView, ResendInvitationAPIView, \
    InvitationVerificationAPIView, UserIntroSlideAPIView

from customers.features.api.views import MyFeatureAPIView

router = routers.DefaultRouter()
router.register('company_user', CompanyUserViewSet,
                base_name='company-user')
router.register('user', UserViewSet, base_name='user')
router.register('my-permission', MyPermissionAPIView)
router.register('my-features', MyFeatureAPIView)
router.register('custom-group', OrganizationGroupViewSet,
                base_name='custom_group'),
router.register('permission_manager', PermissionManagerViewSet,
                base_name='permission_manager')
router.register('send_bulk_invitation', BulkInvitationView,
                base_name='send_bulk_invitation')
router.register('company_information', CompanyInformationViewSet,
                base_name='company_information')
router.register('user_list', UserListViewSet, base_name='UserListViewSet')
router.register('group_list', GroupListViewSet, base_name='group_list')
router.register('company-pending-invitation', ListPendingInvitationViewSet,
                base_name='company-pending-invitation')

app_name = 'authentication'

schema_view = get_swagger_view(title='API Docs')

urlpatterns = [
    # This is for authentication
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('home/', HomeView.as_view(), name='home'),
    # This is for invitations
    path('send-invite/', SendInvite.as_view(),
         name='send-invite'),
    path('send-json-invite/', SendJSONInvite.as_view(),
         name='send-json-invite'),
    path('auth/signup/<str:key>/', AcceptInvite.as_view(),
         name='accept-invite'),
    path('send_reinvite/', send_reinvite, name='send-reinvite'),

]

apis_urls = [
    path('api/login/', LoginAuthentication.as_view(), name='auth-user'),
    path('api/logout/', LogoutAuthentication.as_view(), name='auth-logout'),
    path('api/send-password-reset/<email>/',
         SendResetPasswordAPIView.as_view(),
         name='send-password-reset'),
    path('api/resetpassword/<token>/', ActivateResetPasswordAPIView.as_view(),
         name='activate-password-reset'),
    path('api/member-signup/<token>/', NewCompanySignUpAPIView.as_view(),
         name='member-signup'),
    path('api/invite-member/', InviteMemberAPIView.as_view(),
         name='invite-member'),
    path('api/permission/', PermissionAPIView.as_view(),
         name='permission-list'),
    path('api/permission-types/', PermissionTypeWiseAPIView.as_view(),
         name='permission-list'),
    path('api/group/', GroupAPIView.as_view(), name='group-list'),
    path('api/resend-pending-invite/<id>', ResendInvitationAPIView.as_view(),
         name='resend-pending-invite'),
    path('api/invitation_verification/<token>/',
         InvitationVerificationAPIView.as_view(),
         name='invitation_verification'),
    path('api/introslide/', UserIntroSlideAPIView.as_view(),
         name='introslide'),
    path('api/', include(router.urls)),
]

urlpatterns1 = [
    path('docs/', schema_view),
]
urlpatterns += urlpatterns1 + apis_urls
