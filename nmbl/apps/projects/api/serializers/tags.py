from projects.models import Tag
from rest_framework import serializers


class TagSerializer(serializers.ListField):
    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        from projects.api.serializers import TagBasicSerializer

        return TagBasicSerializer(value, many=True, context=self.context).data


class TagBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            'id',
            'tag',
        )
