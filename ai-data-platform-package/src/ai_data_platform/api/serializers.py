from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework import serializers
from ..models import PlatformConnection, QueryLog
from ..core.encryption import decrypt_api_key

User = get_user_model()

# --- Auth Serializers ---

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password')
        
        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError('Invalid email or password')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        
        attrs['user'] = user
        return attrs

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name']
    
    def create(self, validated_data):
        email = validated_data['email']
        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'email', 'date_joined']

# --- Platform Serializers ---

class PlatformConnectionSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform', read_only=True) # Simple for now
    masked_key = serializers.SerializerMethodField()
    
    class Meta:
        model = PlatformConnection
        fields = ['id', 'platform', 'platform_name', 'masked_key', 'is_valid', 'connected_at', 'metadata']
        read_only_fields = ['id', 'connected_at']
    
    def get_masked_key(self, obj):
        return "••••••••"

class ConnectPlatformSerializer(serializers.Serializer):
    platform = serializers.CharField()
    api_key = serializers.CharField(min_length=10)
    
    def validate_platform(self, value):
        user = self.context.get('request').user
        if PlatformConnection.objects.filter(user=user, platform=value).exists():
           raise serializers.ValidationError(f'{value.title()} is already connected.')
        return value

# --- Query Serializers ---

class ProcessQuerySerializer(serializers.Serializer):
    query = serializers.CharField(min_length=3, max_length=500)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class QueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryLog
        fields = ['id', 'platform', 'query_text', 'response_summary', 'was_successful', 'created_at']
