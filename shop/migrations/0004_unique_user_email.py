"""Enforce email identity without replacing Django's built-in User model.

This database-only constraint belongs to shop because Django's auth migrations
are upstream-owned. Blank emails remain available for administrative accounts.
Existing accounts are preserved, and ambiguous nonblank addresses stop migration
before any records are changed. PostgreSQL is the supported deployment database,
and SQLite supports the local development workflow.
"""
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower, NullIf, Trim


CONSTRAINT_NAME = "unique_normalized_user_email"


def email_constraint():
    return models.UniqueConstraint(
        NullIf(Lower(Trim("email")), models.Value("")),
        name=CONSTRAINT_NAME,
    )


def add_email_constraint(apps, schema_editor):
    if schema_editor.connection.vendor not in ("postgresql", "sqlite"):
        raise RuntimeError("Email identity migration requires PostgreSQL or SQLite")
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    if schema_editor.connection.vendor == "postgresql":
        # Serialize the preflight and index creation with account writes.
        table = schema_editor.quote_name(user_model._meta.db_table)
        schema_editor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
    duplicates = user_model.objects.using(schema_editor.connection.alias).annotate(
        normalized_email=Lower(Trim("email")),
    ).exclude(normalized_email="").values("normalized_email").annotate(
        account_count=models.Count("pk"),
    ).filter(account_count__gt=1).count()
    if duplicates:
        raise RuntimeError(
            f"Email identity migration blocked by {duplicates} duplicate address group(s). "
            "Resolve account ownership through the authorized operator process, then rerun migrate. "
            "No accounts were changed."
        )
    schema_editor.add_constraint(user_model, email_constraint())


def remove_email_constraint(apps, schema_editor):
    schema_editor.remove_constraint(apps.get_model(settings.AUTH_USER_MODEL), email_constraint())


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0003_domainorder_refund_attempted_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(add_email_constraint, remove_email_constraint)]
