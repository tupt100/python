# BaseModel
from nmbl.apps.base.api.serializers import BaseModelDetailSerializer, BaseModelSummarySerializer
from ...models import Feature


class FeatureSummarySerializer(BaseModelSummarySerializer):
    class Meta:
        model = Feature
        fields = [
            'key',
            'value',
        ]

        read_only_fields = [
            'key',
            'value',
        ]


class FeatureDetailSerializer(BaseModelDetailSerializer, FeatureSummarySerializer):
    class Meta:
        model = Feature
        fields = BaseModelDetailSerializer.Meta.fields + FeatureSummarySerializer.Meta.fields + [
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + FeatureSummarySerializer.Meta.read_only_fields + [
        ]
