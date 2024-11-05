# https://github.com/jpadilla/postmark-inbound-python

import json
from base64 import b64decode
from datetime import datetime
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.utils import mktime_tz, parsedate_tz


class PostmarkInbound(object):

    def __init__(self, **kwargs):
        if 'json' not in kwargs:
            raise Exception(
                'Postmark Inbound Error: you must '
                'provide json data')
        self.json = kwargs['json']
        self.source = json.loads(self.json)

    @property
    def subject(self):
        return self.source.get('Subject')

    @property
    def sender(self):
        return self.source.get('FromFull')

    @property
    def to(self):
        return self.source.get('ToFull')

    @property
    def bcc(self):
        return self.source.get('Bcc')

    @property
    def cc(self):
        return self.source.get('CcFull')

    @property
    def reply_to(self):
        return self.source.get('ReplyTo')

    @property
    def mailbox_hash(self):
        return self.source.get('MailboxHash')

    @property
    def tag(self):
        return self.source.get('Tag')

    @property
    def message_id(self):
        return self.source.get('MessageID')

    @property
    def text_body(self):
        return self.source.get('TextBody')

    @property
    def html_body(self):
        return self.source.get('HtmlBody')

    @property
    def headers(self, name='Message-ID'):
        for header in self.source.get('Headers'):
            if header.get('Name') == name:
                return header.get('Value')
        return None

    @property
    def attachments(self, as_mime=False):
        attachments = []
        for attachment in self.source.get('Attachments', []):
            new_attachment = Attachment(attachment)
            if as_mime:
                new_attachment = new_attachment.to_mime()
            attachments.append(new_attachment)
        return attachments

    @property
    def has_attachments(self):
        if not self.attachments:
            return False
        return True

    @property
    def send_date(self):
        date = None
        rfc_2822 = self.source.get('Date')
        if rfc_2822:
            try:
                date = \
                    datetime.fromtimestamp(mktime_tz(parsedate_tz(rfc_2822)))
            except Exception as e:
                print("exception:", e)
                pass
        return date


class Attachment(object):

    def __init__(self, attachment, **kwargs):
        self.attachment = attachment

    def name(self):
        return self.attachment.get('Name')

    def content_type(self):
        return self.attachment.get('ContentType')

    def content_length(self):
        return self.attachment.get('ContentLength')

    def read(self):
        return b64decode(self.attachment.get('Content'))

    def to_mime(self):
        contenttype = self.attachment.get('ContentType').split('/')
        try:
            maintype = contenttype[0]
            subtype = contenttype[1]
        except IndexError:
            raise ValueError('Invalid ContentType')
        mime = MIMEBase(maintype, subtype)
        mime.set_payload(self.read())
        encode_base64(mime)
        mime.add_header(
            'Content-Disposition', 'attachment', filename=self.name())
        return mime

    def download(self, directory='', allowed_content_types=[],
                 max_content_length='', mode='w'):
        if len(directory) == 0:
            raise Exception(
                'Postmark Inbound Error: you must provide'
                ' the upload path')
        if len(
                max_content_length) > 0 and \
                self.content_length() > max_content_length:
            raise Exception(
                'Postmark Inbound Error: the file size '
                'is over %s' % max_content_length)
        if allowed_content_types and \
                self.content_type() not in allowed_content_types:
            raise Exception(
                'Postmark Inbound Error: the file type %s '
                'is not allowed' % self.content_type())
        try:
            if 'b' not in mode:
                mode += 'b'
            attachment = open('%s%s' % (directory, self.name()), mode)
            attachment.write(self.read())
        except IOError:
            raise Exception(
                'Postmark Inbound Error: cannot '
                'save the file, check path and rights.')
        else:
            attachment.close()
