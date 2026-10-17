from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .services import get_profile, is_email_verified

User = get_user_model()


def check_password_strength(password, user=None):
    """Run Django's password validators (min length 10 etc.) and report them under "password"."""
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})


class UserSerializer(serializers.ModelSerializer):
    """The ONLY shape in which a user leaves the API. No password hash, no permissions, no internals."""

    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "avatar_url", "bio", "is_staff", "email_verified", "date_joined"]
        read_only_fields = fields

    def get_display_name(self, obj):
        return get_profile(obj).display_name

    def get_avatar_url(self, obj):
        return get_profile(obj).avatar_url

    def get_bio(self, obj):
        return get_profile(obj).bio

    def get_email_verified(self, obj):
        return is_email_verified(obj)


class RegisterSerializer(serializers.Serializer):
    # NOTE: is_staff / is_superuser are deliberately not accepted here. Staff are never created by public sign-up.
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        check_password_strength(attrs["password"], User(email=attrs["email"]))
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(email=validated_data["email"], password=validated_data["password"])
        name = validated_data.get("display_name", "").strip()
        if name:
            profile = get_profile(user)
            profile.display_name = name
            profile.save(update_fields=["display_name", "updated_at"])
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class ProfileUpdateSerializer(serializers.Serializer):
    """Only these two fields can be changed through PATCH /auth/me/. Anything else in the body is ignored."""

    display_name = serializers.CharField(max_length=80, required=False)
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True)


class EmailVerifySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=500)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, max_length=128)
