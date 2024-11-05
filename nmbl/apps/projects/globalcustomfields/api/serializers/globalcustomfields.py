from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from base.api.serializers import BaseModelSummarySerializer, BaseModelDetailSerializer
from ...models import GlobalCustomField, GlobalCustomFieldAllowedType
from ....serializers import UserSerializer


class AllowContentTypeField(serializers.Field):
    def to_representation(self, value):
        return list(filter(None, [GlobalCustomFieldAllowedType.get_content_type_model(int(item)) for item in value]))

    def to_internal_value(self, data):
        try:
            items = list(
                filter(None, [GlobalCustomFieldAllowedType.get_content_type_value(str(item).lower()) for item in data])
            )
        except:
            items = []
        return items


class GlobalCustomFieldSummarySerializer(BaseModelSummarySerializer):
    allow_content_type = AllowContentTypeField()
    # allow_content_type = serializers.JSONField(read_only=True)

    created_by = UserSerializer(read_only=True)

    class Meta:
        model = GlobalCustomField
        fields = BaseModelSummarySerializer.Meta.fields + [
            'label',
            'created_by',
            'field_type',
            'default_value',
            'is_required',
            'description',
            'is_archive',
            'allow_content_type',
            'created_by_id'
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
            'created_by',
            'created_by_id',
            'is_archive',
        ]


class GlobalCustomFieldDetailSerializer(BaseModelDetailSerializer, GlobalCustomFieldSummarySerializer):
    class Meta:
        model = GlobalCustomField
        fields = BaseModelDetailSerializer.Meta.fields + GlobalCustomFieldSummarySerializer.Meta.fields + [
        ]

        read_only_fields = BaseModelDetailSerializer.Meta.read_only_fields + GlobalCustomFieldSummarySerializer.Meta.read_only_fields + []
