"""Email identity lookup matching the database's normalized uniqueness rule."""
from django.contrib.auth import get_user_model
from django.db.models.functions import Lower, Trim


def email_users(email):
    return get_user_model().objects.alias(
        normalized_email=Lower(Trim("email")),
    ).filter(normalized_email=email.strip().lower())
