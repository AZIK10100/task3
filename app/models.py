from django.db import models
from django.contrib.auth.models import AbstractUser

class StatusChoices(models.TextChoices):
    ("active", "Active"),
    ("blocked", "Blocked"),
    ("expired", "Expired"),


class Card(models.Model):
    card_number = models.CharField(max_length=16, unique=True)
    phone = models.CharField(max_length=13)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=10, choices=StatusChoices.choices)
    expire_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.card_number} ({self.phone})"


class User(AbstractUser):
    telegram_id = models.CharField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    language = models.CharField(max_length=2, default="uz")
    date_of_birth = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.username


class UserCard(models.Model):
    user = models.ForeignKey(User, related_name="cards", on_delete=models.CASCADE)
    card = models.ForeignKey(Card,  on_delete=models.CASCADE, related_name="userscard",)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.id
