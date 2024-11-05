"""nmbl URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from authentication.admin import AuthenticationOrganization, \
    AuthenticationOrgPerm
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from projects.schemas import get_params_swagger_view

from .settings import base

admin.sites.AdminSite.site_header = 'Proxy App Administration'
admin.sites.AdminSite.site_title = 'NMBL site admin'
admin.sites.AdminSite.index_title = 'NMBL admin dashboard'

urlpatterns = static(base.MEDIA_URL, document_root=base.MEDIA_ROOT)
# urlpatterns += static(base.STATIC_URL, document_root=base.STATIC_ROOT)
schema_view = get_params_swagger_view(title='API Docs')

urlpatterns += [
    url(r'^api/docs/', schema_view),
    path('admin/authentication/organization/permission/',
         admin.site.admin_view(AuthenticationOrganization.as_view()),
         name='authentication-organization'),
    path('admin/authentication/organization/<int:pk>/permission/',
         admin.site.admin_view(AuthenticationOrgPerm.as_view()),
         name='organization-permission'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('authentication.urls')),
]

v1_apis = [

    path('projects/', include('projects.urls',
                              namespace='projects')),
    path('notifications/', include('notifications.urls')),
    # path('invitations/', include('invitations.urls',
    # namespace='invitations')),
]

urlpatterns += v1_apis
