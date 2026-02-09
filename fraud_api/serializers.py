from rest_framework import serializers
from django.contrib.auth.models import User
from .models import AMLDetection, CreditAssessment, InsuranceClaim, MarketAlert

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'email')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', '')
        )
        return user

class AMLDetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AMLDetection
        fields = '__all__'

class CreditAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditAssessment
        fields = '__all__'

class InsuranceClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceClaim
        fields = '__all__'

class MarketAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketAlert
        fields = '__all__'
