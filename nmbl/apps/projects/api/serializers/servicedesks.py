from projects.models import (
    ServiceDeskExternalRequest,
    ServiceDeskRequest,
    ServiceDeskUserInformation,
)
from rest_framework import serializers


class RequestTaskListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskRequest
        fields = ('id',)


class ServiceDeskUserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskUserInformation
        fields = (
            'user_name',
            'user_email',
        )


class ServiceDeskRequestBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'service_desk_request',
            'servicedeskuser',
        )

    servicedeskuser = ServiceDeskUserBasicSerializer()


class ServiceDeskRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDeskExternalRequest
        fields = (
            'servicedeskuser',
            'service_desk_request',
        )

    servicedeskuser = ServiceDeskUserBasicSerializer()
    service_desk_request = RequestTaskListSerializer()
