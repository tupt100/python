from base.api.serializers import BaseModelDetailSerializer, BaseModelSummarySerializer
from projects.models import TemplateCustomField


class TemplateCustomFieldSummarySerializer(BaseModelSummarySerializer):
    class Meta:
        model = TemplateCustomField
        fields = BaseModelSummarySerializer.Meta.fields + [
            'label',
            'field_type',
            'default_value',
            'field_type',
            'is_required',
            'description',
            'object_id',
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + []


class TemplateCustomFieldDetailSerializer(BaseModelDetailSerializer, TemplateCustomFieldSummarySerializer):
    class Meta:
        model = TemplateCustomField
        fields = BaseModelDetailSerializer.Meta.fields + TemplateCustomFieldSummarySerializer.Meta.fields + []
        read_only_fields = (
            BaseModelDetailSerializer.Meta.read_only_fields
            + TemplateCustomFieldSummarySerializer.Meta.read_only_fields
            + []
        )
