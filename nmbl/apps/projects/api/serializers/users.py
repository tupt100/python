from authentication.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'user_avatar_thumb')

    user_avatar_thumb = serializers.SerializerMethodField()

    def get_user_avatar_thumb(self, user):
        request = self.context.get("request")
        if user.user_avatar_thumb:
            try:
                user_avatar_thumb_url = user.user_avatar_thumb.url
                return request.build_absolute_uri(user_avatar_thumb_url)
            except Exception as e:
                print("exception:", str(e))
                return None
        else:
            return None


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'first_name',
            'last_name',
        )
