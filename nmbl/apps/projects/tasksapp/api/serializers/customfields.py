from rest_framework import serializers

from nmbl.apps.base.api.serializers import BaseModelSummarySerializer, BaseModelDetailSerializer
from projects.tasksapp.models import CustomField


class CustomFieldSummarySerializer(BaseModelSummarySerializer):
    class Meta:
        model = CustomField
        fields = BaseModelSummarySerializer.Meta.fields + [
            'task_template_id',
            'label',
            'field_type',
            'default_value',
            'is_required',
            'description',
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
        ]


class CustomFieldDetailSerializer(BaseModelDetailSerializer, CustomFieldSummarySerializer):
    task_template_id = serializers.IntegerField(required=True, )

    class Meta:
        model = CustomField
        fields = BaseModelDetailSerializer.Meta.fields + CustomFieldSummarySerializer.Meta.fields + [
        ]

        read_only_fields = BaseModelDetailSerializer.Meta.read_only_fields + CustomFieldSummarySerializer.Meta.read_only_fields + [
        ]
