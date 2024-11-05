from authentication.app_settings import app_settings
from authentication.utils import import_attribute
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text


# Code credits here to django-allauth
class BaseInvitationsAdapter(object):
    def stash_verified_email(self, request, email):
        request.session['account_verified_email'] = email

    def unstash_verified_email(self, request):
        ret = request.session.get('account_verified_email')
        request.session['account_verified_email'] = None
        return ret

    def format_email_subject(self, subject):
        # prefix = app_settings.EMAIL_SUBJECT_PREFIX
        # if prefix is None:
        #     # site = Site.objects.get_current()
        #     # prefix = "[{name}] ".format(name=site.name)
        #     prefix = "[{name}] ".format(name="PROXY")
        prefix = "[{name}] ".format(name="PROXY")
        return prefix + force_text(subject)

    def render_mail(self, template_prefix, email,
                    context, subject, from_email):
        """
        Renders an e-mail to `email`.  `template_prefix` identifies the
        e-mail that is to be sent, e.g. "account/email/email_confirmation"
        """
        subject = subject
        # remove superfluous line breaks
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)
        bodies = {}
        for ext in ['html', 'txt']:
            try:
                template_name = '{0}_message.{1}'.format(template_prefix, ext)
                bodies[ext] = render_to_string(
                    template_name, context).strip()
            except TemplateDoesNotExist:
                if ext == 'txt' and not bodies:
                    # We need at least one body
                    raise
        if 'txt' in bodies:
            msg = EmailMultiAlternatives(
                subject, bodies['txt'], from_email, [email])
            if 'html' in bodies:
                msg.attach_alternative(bodies['html'], 'text/html')
        else:
            msg = EmailMessage(
                subject, bodies['html'], from_email, [email])
            msg.content_subtype = 'html'  # Main content is now text/html
        return msg

    def send_mail(self, template_prefix, email,
                  context, subject=None,
                  from_email=settings.DEFAULT_FROM_EMAIL):
        msg = self.render_mail(template_prefix, email,
                               context, subject, from_email)
        msg.send()

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

    def clean_email(self, email):
        """
        Validates an email value. You can hook into this if you want to
        (dynamically) restrict what email addresses can be chosen.
        """
        return email

    def add_message(self, request, level, message_template,
                    message_context=None, extra_tags=''):
        """
        Wrapper of `django.contrib.messages.add_message`, that reads
        the message text from a template.
        """
        if 'django.contrib.messages' in settings.INSTALLED_APPS:
            try:
                if message_context is None:
                    message_context = {}
                # message = render_to_string(
                #  message_template, message_context).strip()
                message = render_to_string(
                    message_template, message_context)
                if message:
                    messages.add_message(
                        request, level, message, extra_tags=extra_tags)
            except TemplateDoesNotExist:
                pass


def get_invitations_adapter():
    return import_attribute(app_settings.ADAPTER)()
