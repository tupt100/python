import requests
from authentication.models import BaseModel
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


def validate_attachment_external_url(value):
    """
    1. validation google drive url
    2. validation file exists
    """
    if value.find("https://docs.google.com/") != 0:
        raise ValidationError(_("Please insert a valid Google Doc"))

    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}
    session.headers.update(headers)
    response = session.get(value, headers=session.headers)
    if response.status_code >= 400:
        raise ValidationError(_("Please insert a valid Google Doc"))


class AttachmentQuerySet(models.QuerySet):
    # TODO: remove all uncontrolled queries, use only get_by_content_type and get_by_object_id
    # TODO: remove fields task_id, project_id and workflow_id and use only content_type and object_id
    def get_by_content_type(self, content_type):
        return self.filter(content_type=content_type)

    def get_by_object_id(self, object_id):
        return self.filter(object_id=object_id)

    def get_by_content_type_and_object_id(self, content_type, object_id):
        return self.filter(content_type=content_type, object_id=object_id)

    def get_by_instance(self, instance):
        content_type = ContentType.objects.get_for_model(instance)
        return self.get_by_content_type_and_object_id(content_type, instance.id)


class AttachmentManager(models.Manager):
    def get_queryset(self):
        return AttachmentQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().filter(is_delete=False)

    def duplicate_instance(self, pk):
        obj = self.get(pk=pk)
        if not obj.document:
            obj.pk = None
            obj.save()
            return obj
        copy_doc_name = get_random_string(20) + "." + obj.document.name.split('.')[-1]
        file_path = "Documents/{}".format(copy_doc_name)
        read_file = default_storage.open(obj.document.name, 'rb')
        write_file = default_storage.open(file_path, 'wb')
        write_file.write(read_file.read())
        read_file.close()
        write_file.close()
        obj.document.name = file_path
        # clone the attachment object with new file.
        obj.pk = None
        obj.save()
        return obj


class Attachment(BaseModel):
    """
    Here attachment/document can be link
        with Document/Project/Workflow
    """

    document_name = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )
    document = models.FileField(
        null=True,
        blank=True,
        upload_to='Documents/',
    )
    external_url = models.URLField(
        validators=[
            validate_attachment_external_url,
        ],
        null=True,
        blank=True,
        verbose_name=_('External URL'),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        default=None,
        blank=True,
        null=True,
    )
    object_id = models.PositiveIntegerField(
        default=None,
        blank=True,
        null=True,
    )
    content_object = GenericForeignKey(
        'content_type',
        'object_id',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        verbose_name=_('Created By'),
        on_delete=models.SET_NULL,
        related_name='attachment_created_by',
    )
    organization = models.ForeignKey(
        'authentication.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='attachment_organization',
        verbose_name=_('Company'),
    )
    document_tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='document_tags',
        verbose_name=_('Document Tag'),
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name=_('Is Delete'),
    )
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_attachment',
    )
    workflow = models.ForeignKey(
        'Workflow',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_attachment',
    )
    task = models.ForeignKey(
        'Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_attachment',
    )
    uploaded_by = models.ForeignKey(
        'ServiceDeskUserInformation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='servicedeskuser_attachment',
    )
    message_document = models.ForeignKey(
        'ServiceDeskRequestMessage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='servicedesk_message_attachment',
    )

    objects = AttachmentManager()

    def __str__(self):
        return str(self.content_type or self.document)

    def clean(self):
        if self.external_url and not self.document_name:
            raise ValidationError({'document_name': [_('This field is required')]})
        if self.external_url and self.document:
            error_msg = _('Please insert just external_url or document field')
            raise ValidationError(
                {
                    'external_url': [error_msg],
                    'document': [error_msg],
                }
            )
        if not self.external_url and not self.document:
            error_msg = _('Please insert at least external_url or document field')
            raise ValidationError(
                {
                    'external_url': [error_msg],
                    'document': [error_msg],
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Attachment, self).save(*args, **kwargs)

    @property
    def url(self):
        return self.external_url if self.external_url else self.document.url
