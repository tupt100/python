from base.api.serializers import BaseModelDetailSerializer, BaseModelSummarySerializer
from django.contrib.auth import get_user_model
from projects.models import BaseTemplateModel, WorkGroup
from rest_framework import serializers

from ..users import UserSerializer
from ..workgroups import CompanyWorkGroupBasicSerializer

User = get_user_model()


# TODO: handle user created by
class BaseTemplateSummarySerializer(BaseModelSummarySerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = BaseTemplateModel
        fields = BaseModelSummarySerializer.Meta.fields + [
            'title',
            'name',
            'importance',
            'due_date',
            'created_by',
        ]

        read_only_fields = BaseModelSummarySerializer.Meta.read_only_fields + [
            'is_delete',
        ]


class BaseTemplateDetailSerializer(BaseModelDetailSerializer, BaseTemplateSummarySerializer):
    assigned_to_group_id = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        allow_empty=True,
        allow_null=True,
        required=False,
        queryset=WorkGroup.objects.all(),
        source='assigned_to_group',
    )
    assigned_to_group = CompanyWorkGroupBasicSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = BaseTemplateModel
        fields = (
            BaseModelDetailSerializer.Meta.fields
            + BaseTemplateSummarySerializer.Meta.fields
            + [
                'assigned_to_group',
                'assigned_to_group_id',
                'start_date',
                'description',
                'is_private',
                'attorney_client_privilege',
                'work_product_privilege',
                'confidential_privilege',
                'is_delete',
            ]
        )

        read_only_fields = (
            BaseModelDetailSerializer.Meta.read_only_fields + BaseTemplateSummarySerializer.Meta.read_only_fields + []
        )
