from projects.models import Project
from rest_framework import serializers


class ProjectBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            'id',
            'name',
        )
