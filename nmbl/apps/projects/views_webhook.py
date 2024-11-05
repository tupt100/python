from authentication.models import User, GroupAndPermission
from base.services.postmark import PostmarkInbound
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.conf import settings

from urllib.parse import urlparse
import re

from .helpers import (
    handle_webhook_task_inbound,
    handle_webhook_project_inbound,
    handle_webhook_workflow_inbound,
    handle_message_task_inbound,
    handle_message_project_inbound,
    handle_message_workflow_inbound,
    handle_webhook_request_inbound,
    task_message_inbound_webhook,
    project_message_inbound_webhook,
    workflow_message_inbound_webhook)
from .models import Workflow


def email_address_contains_proxy_domain(email_address):
    email_address = email_address.lower()
    site_domain = urlparse(settings.SITE_URL).netloc
    domain_regex = site_domain.format('(.+)')
    return re.match(domain_regex, email_address) != None


@method_decorator(csrf_exempt, name='dispatch')
class PostmarkTaskWebHook(View):

    def get(self, request, *args, **kwargs):
        print('PostmarkTaskWebHook GET: ', request.GET)
        return JsonResponse({'status': 'ok'})

    def post(self, request, *args, **kwargs):
        return JsonResponse({'status': 'ok'})
        data = request.body.decode('utf-8')
        return handle_webhook_task_inbound(data)


@method_decorator(csrf_exempt, name='dispatch')
class PostmarkProjectWebHook(View):

    def get(self, request, *args, **kwargs):
        print('PostmarkWorkflowWebHook GET: ', request.GET)
        return JsonResponse({'status': 'ok'})

    def post(self, request, *args, **kwargs):
        return JsonResponse({'status': 'ok'})
        data = request.body.decode('utf-8')
        return handle_webhook_project_inbound(data)


@method_decorator(csrf_exempt, name='dispatch')
class PostmarkCommonWebHook(View):

    def get(self, request, *args, **kwargs):
        print('PostmarkWorkflowWebHook GET: ', request.GET)
        return JsonResponse({'status': 'ok'})

    def post(self, request, *args, **kwargs):
        data = request.body.decode('utf-8')
        postmark_obj = PostmarkInbound(json=data)
        if postmark_obj.to:
            targets_email = map(lambda x: x['Email'].lower(), postmark_obj.to)
            response = []
            for target_email in targets_email:
                if target_email.startswith("task@"):
                    response.append(handle_webhook_task_inbound(data))
                if target_email.startswith("project@"):
                    response.append(handle_webhook_project_inbound(data))
                if target_email.startswith("workflow@"):
                    response.append(handle_webhook_workflow_inbound(data))
                if target_email.startswith("tk"):
                    response.append(handle_message_task_inbound(data))
                if target_email.startswith("wf"):
                    response.append(handle_message_workflow_inbound(data))
                if target_email.startswith("pj"):
                    response.append(handle_message_project_inbound(data))
                if target_email.startswith("requests@"):
                    response.append(handle_webhook_request_inbound(data))
            if len(response) > 0:
                return response[0]
        email = []
        if postmark_obj.to:
            for to_email in postmark_obj.to:
                if email_address_contains_proxy_domain(to_email['Email'].lower()):
                    email.append(to_email['Email'].lower())
        if postmark_obj.cc:
            for cc_email in postmark_obj.cc:
                if email_address_contains_proxy_domain(cc_email['Email'].lower()):
                    email.append(cc_email['Email'].lower())
        if postmark_obj.bcc:
            for bcc_email in postmark_obj.bcc:
                if email_address_contains_proxy_domain(bcc_email['Email'].lower()):
                    email.append(bcc_email['Email'].lower())
        if email:
            target_email = email[0]
            if target_email.startswith("task_"):
                return task_message_inbound_webhook(data, target_email)
            if target_email.startswith("workflow_"):
                return workflow_message_inbound_webhook(data, target_email)
            if target_email.startswith("project_"):
                return project_message_inbound_webhook(data, target_email)
        return JsonResponse({'status': '400'})


@method_decorator(csrf_exempt, name='dispatch')
class PostmarkWorkflowWebHook(View):

    def get(self, request, *args, **kwargs):
        print('PostmarkWorkflowWebHook GET: ', request.GET)
        return JsonResponse({'status': 'ok'})

    def post(self, request, *args, **kwargs):
        data = request.body.decode('utf-8')
        postmark_obj = PostmarkInbound(json=data)
        from_email = postmark_obj.sender.get('Email').lower()
        print('from_email: ', from_email)
        user = User.objects.filter(email=from_email).last()
        print('user: ', user)
        if user:
            company = user.company
            group = user.group
            permission_category = 'workflow'
            slug = permission_category + "_" + permission_category + '-create'
            group_permission = GroupAndPermission.objects.filter(
                group=group, company=company,
                permission__permission_category=permission_category,
                permission__slug=slug, has_permission=True).exists()
            if not group_permission:
                return
            post_data = {
                'name': postmark_obj.subject,
                'description': postmark_obj.text_body,
                'organization': company,
                'importance': 1,  # default importance is Med
            }
            if len(postmark_obj.to) > 1:
                to_email = postmark_obj.to[1]['Email']
                user = User.objects.filter(
                    email=to_email, company=company).last()
                if user:
                    post_data['owner'] = user
            assigned_to_users = []
            if len(postmark_obj.cc) > 1:
                for assignee in postmark_obj.cc:
                    assignee_email = assignee['Email']
                    user = User.objects.filter(
                        email=assignee_email, company=company).last()
                    if user:
                        assigned_to_users.append(user)
                # if assigned_to_users:
                #     post_data['assigned_to_users'] = assigned_to_users
            print(post_data, )
            workflow = Workflow.objects.create(**post_data)
            if assigned_to_users:
                for assignee in assigned_to_users:
                    workflow.assigned_to_users.add(assignee)
        return JsonResponse({'status': 'ok'})


class TemplateTestView(TemplateView):
    template_name = "password_reset/password_reset_message.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
