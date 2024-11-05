from django.urls import path, include
from notifications.views import NotificationViewSet, \
    AskTaskUpdateAPIView, CompanyUserNotificationSettingViewSet,\
    UserNotificationSettingViewSet, \
    CompanyUserNotificationViewSet, UserNotificationViewSet
from rest_framework import routers

app_name = 'notifications'
router = routers.DefaultRouter()
router.register('notification', NotificationViewSet,
                base_name="notification")
router.register('company_user_notification',
                CompanyUserNotificationSettingViewSet)
router.register('user_notification', UserNotificationSettingViewSet)
router.register('company_user_notification_settings',
                CompanyUserNotificationViewSet,
                basename='company_user_notification_settings')
router.register('user_notification_settings', UserNotificationViewSet,
                basename='user_notification_settings')

urlpatterns = [

    path('api/', include(router.urls)),
    path('api/taskupdate/', AskTaskUpdateAPIView.as_view()),
]
