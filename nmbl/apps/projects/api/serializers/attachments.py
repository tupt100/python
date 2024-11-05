from base.constants import DATE_FORMAT_OUT
from projects.helpers import AuditHistoryCreate, GetOrCreateTags
from projects.models import Attachment
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .tags import TagBasicSerializer
from .users import UserSerializer


def get_attachment_url(request, obj):
    return request.build_absolute_uri(obj.url)


class AttachmentPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super(AttachmentPrimaryKeyRelatedField, self).get_queryset()
        if not request or not queryset:
            return queryset.none()
        return queryset.filter(organization=request.user.company)

    def to_representation(self, value):
        return AttachmentBasicSerializer(value, context=self.context).data


class AttachmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = [
            'document',
            'document_name',
            'document_tag_save',
            'external_url',
            'document_url',
        ]
        read_only_fields = [
            'document_url',
        ]

    document = serializers.FileField(
        allow_empty_file=True,
        allow_null=True,
        required=False,
    )
    document_tag_save = serializers.CharField(required=False)
    external_url = serializers.URLField(
        allow_null=True,
        allow_blank=True,
        required=False,
        write_only=True,
    )
    document_url = serializers.SerializerMethodField()

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organization or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't upload Documents"})
        attrs['organization'] = request.user.company
        attrs['created_by'] = request.user
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        document_tag_save = validated_data.pop('document_tag_save', None)
        instance = super(AttachmentCreateSerializer, self).create(validated_data)
        AuditHistoryCreate("attachment", instance.id, request.user, "Date uploaded:")
        tag_list = []
        if document_tag_save:
            document_tags = document_tag_save.split(",")
            for document_tag in document_tags:
                tag_list.append(GetOrCreateTags(document_tag, instance.organization))
        instance.document_tags.set(tag_list)
        return instance

    def get_document_url(self, obj):
        return get_attachment_url(self.context['request'], obj)


class AttachmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ('id', 'document_name', 'document_tag_save', 'document_url')
        read_only_fields = [
            'document_url',
        ]

    document_tag_save = serializers.CharField(required=False, allow_blank=True)
    document_url = serializers.SerializerMethodField()

    def validate(self, attrs):
        request = self.context.get('request')
        # Check whether user belongs to any organisation or not
        if not request.user.company:
            raise ValidationError({"detail": "You are not part of any organisation, " "So you can't upload Documents"})
        return attrs

    def update(self, instance, validated_data):
        if 'document_tag_save' in validated_data.keys():
            doc_tag_list = []
            document_tags = validated_data.pop('document_tag_save', None)
            if document_tags:
                document_tags = document_tags.split(",")
                for document_tags in document_tags:
                    doc_tag_list.append(GetOrCreateTags(document_tags, instance.organization))
            instance.document_tags.set(doc_tag_list)
        instance = super(AttachmentUpdateSerializer, self).update(instance, validated_data)
        return instance

    def get_document_url(self, obj):
        return get_attachment_url(self.context['request'], obj)


class AttachmentListSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id',
            'document_name',
            'document',
            'created_at',
            'uploaded_to',
            'created_by',
            'document_url',
        ]
        read_only_fields = [
            'document_url',
        ]

    uploaded_to = serializers.SerializerMethodField()
    document_name = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    def get_created_by(self, obj):
        if obj.created_by:
            request = self.context.get("request")
            return UserSerializer(obj.created_by, context={'request': request}).data
        elif obj.uploaded_by:
            return obj.uploaded_by.user_name
        else:
            return None

    def get_document_name(self, obj):
        if obj.document_name:
            return obj.document_name
        return obj.document.name.replace('Documents/', '')

    def get_uploaded_to(self, obj):
        if obj.project:
            return {'name': obj.project.name, 'is_private': obj.project.is_private}
        elif obj.workflow:
            return {'name': obj.workflow.name, 'is_private': obj.workflow.is_private}

        elif obj.task:
            return {'name': obj.task.name, 'is_private': obj.task.is_private}
        else:
            return None

    def get_document_url(self, obj):
        return get_attachment_url(self.context['request'], obj)


class AttachmentDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'document_name',
            'document',
            'created_at',
            'uploaded_to',
            'created_by',
            'document_tags',
            'document_url',
        )
        read_only_fields = [
            'document_url',
        ]

    uploaded_to = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format=DATE_FORMAT_OUT)
    document_name = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    document_tags = TagBasicSerializer(many=True)
    document_url = serializers.SerializerMethodField()

    def get_created_by(self, obj):
        if obj.created_by:
            request = self.context.get("request")
            return UserSerializer(obj.created_by, context={'request': request}).data
        elif obj.uploaded_by:
            return obj.uploaded_by.user_name
        else:
            return None

    def get_document_name(self, obj):
        if obj.document_name:
            return obj.document_name
        return obj.document.name.replace('Documents/', '')

    def get_uploaded_to(self, obj):
        detail = {}
        if obj.project:
            detail = {
                'id': obj.project.pk,
                'name': obj.project.name,
                'importance': obj.project.importance,
                'is_private': obj.project.is_private,
            }
            return detail
        elif obj.workflow:
            detail = {
                'id': obj.workflow.pk,
                'name': obj.workflow.name,
                'importance': obj.workflow.importance,
                'is_private': obj.workflow.is_private,
            }
            return detail
        elif obj.task:
            detail = {
                'id': obj.task.pk,
                'name': obj.task.name,
                'importance': obj.task.importance,
                'is_private': obj.task.is_private,
            }
            return detail
        else:
            return detail

    def get_document_url(self, obj):
        return get_attachment_url(self.context['request'], obj)


class DocumentDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'document_name',
            'document_url',
            'created_by',
            'created_at',
        )
        read_only_fields = [
            'document_url',
        ]

    document_name = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    def get_created_by(self, obj):
        if obj.created_by:
            return obj.created_by.first_name + " " + obj.created_by.last_name
        elif obj.uploaded_by:
            return obj.uploaded_by.user_name
        else:
            return None

    def get_document_name(self, obj):
        if obj.document_name:
            return obj.document_name
        return obj.document.name.replace('Documents/', '')

    def get_document_url(self, obj):
        return get_attachment_url(self.context['request'], obj)


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'document_name',
        )


class DocumentBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'attachment_name',
        )

    attachment_name = serializers.SerializerMethodField()

    def get_attachment_name(self, obj):
        try:
            if obj.document_name:
                return obj.document_name
            return obj.document.name.split('/')[-1]
        except Exception as e:
            print("exception:", str(e))
            return obj.document.name if obj.document else None


class AttachmentBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ('id', 'attachment_name', 'attachment_url', 'document_tags')

    attachment_name = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    document_tags = serializers.SerializerMethodField()

    def get_attachment_name(self, obj):
        try:
            if obj.document_name:
                return obj.document_name
            return obj.document.name.split('/')[-1]
        except Exception as e:
            print("exception:", str(e))
            return obj.document.name if obj.document else ''

    def get_attachment_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.document.url)

    def get_document_tags(self, obj):
        return obj.document_tags.values('id', 'tag')


class DocumentBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            'id',
            'document_name',
            'document',
        )

    document_name = serializers.SerializerMethodField()

    def get_document_name(self, obj):
        if obj.document_name:
            return obj.document_name
        return obj.document.name.replace('Documents/', '')
