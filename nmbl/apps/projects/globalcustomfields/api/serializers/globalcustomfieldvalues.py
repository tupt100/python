from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .globalcustomfields import GlobalCustomFieldSummarySerializer
from base.api.serializers import BaseModelSummarySerializer, BaseModelDetailSerializer

from ...models import GlobalCustomFieldValue, GlobalCustomFieldAllowedType


class ContentTypeField(serializers.Field):
    def to_representation(self, value):
        return GlobalCustomFieldAllowedType.get_content_type_model(value)

    def to_internal_value(self, data):
        return GlobalCustomFieldAllowedType.get_content_type_value(data.lower())


class GlobalCustomFieldValueSummarySerializer(BaseModelSummarySerializer):
    global_custom_field = GlobalCustomFieldSummarySerializer(read_only=True)
    global_custom_field_id = serializers.IntegerField(required=True, )
    content_type = ContentTypeField(source='content_type_id')

    class Meta:
        model = GlobalCustomFieldValue
        fields = BaseModelSummarySerializer.Meta.fields + [
            'value',
            'is_archive',
            'object_id',
            'content_type',
            'global_custom_field_id',
            'global_custom_field',

        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
            'is_archive',
            'global_custom_field'
        ]


class GlobalCustomFieldValueDetailSerializer(BaseModelDetailSerializer, GlobalCustomFieldValueSummarySerializer):
    class Meta:
        model = GlobalCustomFieldValue
        fields = BaseModelDetailSerializer.Meta.fields + GlobalCustomFieldValueSummarySerializer.Meta.fields + [
        ]

        read_only_fields = BaseModelDetailSerializer.Meta.read_only_fields + GlobalCustomFieldValueSummarySerializer.Meta.read_only_fields + []
