from typing import Any, Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.business.models import Feature
from apps.tenancies.models import Tenant


class AuditLog(models.Model):
    """
    Audit log for important system actions.
    Uses Django's GenericForeignKey to point to any other model.
    Corresponds to the 'audit_logs' table.
    """

    class ActorType(models.TextChoices):
        USER = "user", _("User")
        SYSTEM = "system", _("System")
        API_KEY = "api_key", _("API Key")

    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    actor_id: models.ForeignKey[Optional[settings.AUTH_USER_MODEL]] = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("actor"),
    )
    actor_type: models.CharField[str] = models.CharField(
        _("actor type"),
        max_length=255,
        choices=ActorType.choices,
        default=ActorType.USER,
        help_text=_(
            "Distinguishes if the actor was a user, a system process, or an API Key."
        ),
    )
    action: models.CharField[str] = models.CharField(
        _("action"),
        max_length=255,
        help_text=_("E.g., 'user.login', 'invoice.created'"),
    )

    target_content_type: models.ForeignKey[Optional[ContentType]] = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("object type"),
    )
    target_object_id: models.CharField[Optional[str]] = models.CharField(
        _("object ID"), max_length=255, null=True, blank=True
    )
    target: GenericForeignKey = GenericForeignKey(
        "target_content_type", "target_object_id"
    )
    details: models.JSONField[Optional[Any]] = models.JSONField(
        _("details"), null=True, blank=True
    )
    ip_address: models.GenericIPAddressField[Optional[str]] = (
        models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    )
    created_at: models.DateTimeField = models.DateTimeField(
        _("created at"), auto_now_add=True
    )

    data_before: models.JSONField[Optional[Any]] = models.JSONField(
        _("data before"),
        null=True,
        blank=True,
        help_text=_("Object state (JSON) before the change (for UPDATE and DELETE)."),
    )
    data_after: models.JSONField[Optional[Any]] = models.JSONField(
        _("data after"),
        null=True,
        blank=True,
        help_text=_("Object state (JSON) after the change (for CREATE and UPDATE)."),
    )
    trace_id: models.CharField[Optional[str]] = models.CharField(
        _("trace ID"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_(
            "Correlation ID to track a chain of events across microservices or processes."
        ),
    )
    reason: models.TextField[Optional[str]] = models.TextField(
        _("reason"),
        null=True,
        blank=True,
        help_text=_(
            "A field for the user or system to explain the reason for the change."
        ),
    )
    changed_fields: models.JSONField[Optional[Any]] = models.JSONField(
        _("changed fields"),
        null=True,
        blank=True,
        help_text=_("Fields that were changed (for UPDATE operations)."),
    )
    context: models.JSONField[Optional[Any]] = models.JSONField(
        _("context"),
        null=True,
        blank=True,
        help_text=_("Additional context for the action."),
    )
    user_agent: models.TextField[Optional[str]] = models.TextField(
        _("user agent"), null=True, blank=True
    )
    request_id: models.CharField[Optional[str]] = models.CharField(
        _("request ID"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Request ID for tracing."),
    )
    checksum: models.BinaryField[Optional[bytes]] = models.BinaryField(
        _("checksum"),
        null=True,
        blank=True,
        help_text=_("Checksum for data integrity."),
    )

    class Meta:
        db_table: str = "audit_logs"
        verbose_name: str = _("audit log")
        verbose_name_plural: str = _("audit logs")
        ordering: list[str] = ["-created_at"]
        indexes: list[models.Index] = [
            models.Index(
                fields=["tenant", "-created_at"],
                name="idx_logs_tenant_created_at",
            ),
            models.Index(
                fields=["target_content_type", "target_object_id"],
                name="idx_audit_logs_target",
            ),
        ]


class AuditMetric(models.Model):
    """
    Stores usage metrics for metered features.
    Corresponds to the 'audit_metrics' table.
    """

    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    feature: models.ForeignKey[Feature] = models.ForeignKey(
        Feature, on_delete=models.CASCADE, verbose_name=_("feature")
    )
    quantity_used: models.BigIntegerField = models.BigIntegerField(_("quantity used"))
    measured_at: models.DateTimeField = models.DateTimeField(
        _("measured at"), auto_now_add=True
    )

    class Meta:
        db_table: str = "audit_metrics"
        verbose_name: str = _("audit metric")
        verbose_name_plural: str = _("audit metrics")
        unique_together: list[list[str]] = [["tenant", "feature", "measured_at"]]
        indexes: list[models.Index] = [
            models.Index(fields=["tenant"], name="idx_audit_metrics_tenant_id"),
            models.Index(fields=["feature"], name="idx_audit_metrics_feature_id"),
        ]


class MetadataAudit(models.Model):
    """
    Audits changes to metadata tables.
    Corresponds to the 'metadata_audit' table.
    """

    class Operation(models.TextChoices):
        INSERT = "INSERT", _("Insert")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")

    table_name: models.CharField[str] = models.CharField(
        _("table name"), max_length=255
    )
    record_id: models.CharField[str] = models.CharField(
        _("record ID"),
        max_length=255,
        help_text=_("Supports non-integer primary keys."),
    )
    operation: models.CharField[str] = models.CharField(
        _("operation"), max_length=10, choices=Operation.choices
    )
    before_state: models.JSONField[Optional[Any]] = models.JSONField(
        _("before state"), null=True, blank=True
    )
    after_state: models.JSONField[Optional[Any]] = models.JSONField(
        _("after state"), null=True, blank=True
    )
    changed_at: models.DateTimeField = models.DateTimeField(
        _("changed at"), auto_now_add=True
    )
    changed_by_user: models.ForeignKey[
        Optional[settings.AUTH_USER_MODEL]
    ] = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("changed by"),
    )
    tenant: models.ForeignKey[Optional[Tenant]] = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("tenant"),
    )

    class Meta:
        db_table: str = "metadata_audit"
        verbose_name: str = _("metadata audit")
        verbose_name_plural: str = _("metadata audits")


class AuditLogSignature(models.Model):
    """
    Digital signature for an audit log entry to ensure integrity.
    Corresponds to the 'audit_log_signatures' table.
    """

    audit_log: models.OneToOneField[AuditLog] = models.OneToOneField(
        AuditLog,
        on_delete=models.CASCADE,
        primary_key=True,
        verbose_name=_("audit log"),
    )
    signature: models.BinaryField = models.BinaryField(_("signature"))
    signed_at: models.DateTimeField = models.DateTimeField(
        _("signed at"), auto_now_add=True
    )
    signer_user: models.ForeignKey[settings.AUTH_USER_MODEL] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_("signer")
    )

    class Meta:
        db_table: str = "audit_log_signatures"
        verbose_name: str = _("audit log signature")
        verbose_name_plural: str = _("audit log signatures")


class SensitiveAccessLog(models.Model):
    """
    Logs access to sensitive data.
    Corresponds to the 'sensitive_access_logs' table.
    """

    user: models.ForeignKey[settings.AUTH_USER_MODEL] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("user")
    )
    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    accessed_table: models.CharField[str] = models.CharField(
        _("accessed table"), max_length=255
    )
    accessed_key: models.CharField[str] = models.CharField(
        _("accessed key"), max_length=255
    )
    accessed_at: models.DateTimeField = models.DateTimeField(
        _("accessed at"), auto_now_add=True
    )
    query_params: models.JSONField[Optional[Any]] = models.JSONField(
        _("query params"), null=True, blank=True
    )

    class Meta:
        db_table: str = "sensitive_access_logs"
        verbose_name: str = _("sensitive access log")
        verbose_name_plural: str = _("sensitive access logs")
