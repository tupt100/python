from rest_framework import serializers

# BaseModel
from nmbl.apps.base.db import BaseModel


class BaseModelSummarySerializer(serializers.ModelSerializer):
    class Meta:
        abstract = True
        model = BaseModel
        fields = [
            'pk',
            'created_at',
            'update_at',
            'is_active',
        ]

        read_only_fields = [
            'pk',
            'created_at',
            'update_at',
            'is_active',
        ]


class BaseModelDetailSerializer(BaseModelSummarySerializer):
    class Meta:
        abstract = True
        model = BaseModel
        fields = BaseModelSummarySerializer.Meta.fields + [
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
        ]
