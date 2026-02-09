from django.db import models

class AMLDetection(models.Model):
    transaction_id = models.CharField(max_length=100)
    amount = models.FloatField(default=0.0)
    sender_id = models.CharField(max_length=100, blank=True, null=True)
    receiver_id = models.CharField(max_length=100, blank=True, null=True)
    risk_score = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    alerts = models.JSONField(default=list)

class CreditAssessment(models.Model):
    APPROVED = 'APPROVED'
    DECLINED = 'DECLINED'
    MANUAL_REVIEW = 'MANUAL_REVIEW'
    
    DECISION_CHOICES = [
        (APPROVED, 'Approved'),
        (DECLINED, 'Declined'),
        (MANUAL_REVIEW, 'Manual Review'),
    ]
    
    applicant_id = models.CharField(max_length=100)
    risk_score = models.FloatField()
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    alerts = models.JSONField(default=list, blank=True)

class InsuranceClaim(models.Model):
    claim_id = models.CharField(max_length=100)
    policy_id = models.CharField(max_length=100, blank=True, null=True)
    claim_amount = models.FloatField(default=0.0)
    fraud_risk = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    alerts = models.JSONField(default=list)

class MarketAlert(models.Model):
    symbol = models.CharField(max_length=100)
    price = models.FloatField(default=0.0)
    volume = models.FloatField(default=0.0)
    manipulation_risk = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    alerts = models.JSONField(default=list)
