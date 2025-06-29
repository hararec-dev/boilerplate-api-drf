from typing import Any, Optional, TYPE_CHECKING, List, Dict

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseAuditModel, TimestampedModel

if TYPE_CHECKING:
    from apps.users.models import User


class Tenant(BaseAuditModel):
    """
    Represents a tenant in the system. Each tenant is an isolated entity
    with its own users, organizations, and data.
    Corresponds to the 'tenants' table.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        DELETED = "deleted", _("Deleted")
        PENDING_SETUP = "pending_setup", _("Pending setup")
        TRIAL = "trial", _("Trial")

    name: models.CharField[str] = models.CharField(_("name"), max_length=255)
    slug: models.SlugField[str] = models.SlugField(
        _("slug"),
        max_length=100,
        unique=True,
        help_text=_("Unique URL identifier, e.g. 'my-company'"),
    )
    domain: models.CharField[Optional[str]] = models.CharField(
        _("domain"),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Custom domain for the tenant"),
    )
    status: models.CharField[str] = models.CharField(
        _("status"), max_length=50, choices=Status.choices, default=Status.PENDING_SETUP
    )
    parent_tenant: models.ForeignKey["Tenant", Optional["Tenant"]] = models.ForeignKey(
        "self",
        verbose_name=_("parent tenant"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("For hierarchical structures (resellers, etc.)"),
    )
    onboarding_completed_at: models.DateTimeField[Optional[Any]] = models.DateTimeField(
        _("onboarding completed at"), null=True, blank=True
    )
    available_credits: models.DecimalField = models.DecimalField(
        _("available credits"), max_digits=12, decimal_places=2, default=0
    )
    billing_strategy: models.CharField[str] = models.CharField(
        _("billing strategy"), max_length=50, default="subscription"
    )
    data_retention_policy: models.JSONField[Optional[Any]] = models.JSONField(
        _("data retention policy"), null=True, blank=True
    )

    roles: "models.Manager[Role]"

    def __str__(self) -> str:
        return self.name

    class Meta:
        db_table: str = "tenants"
        verbose_name: str = _("tenant")
        verbose_name_plural: str = _("tenants")
        ordering: list[str] = ["name"]


class TenantConfiguration(TimestampedModel):
    """
    Specific configurations for each tenant, such as branding, localization,
    and custom settings.
    Corresponds to the 'tenant_configurations' table.
    """

    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE
    )
    data_residency_region: models.CharField[str] = models.CharField(
        _("data residency region"), max_length=50, default="us-east-1"
    )
    timezone: models.CharField[str] = models.CharField(
        _("timezone"), max_length=50, default="UTC"
    )
    locale: models.CharField[str] = models.CharField(
        _("locale"), max_length=10, default="en-US"
    )
    branding: models.JSONField[Dict[str, Any]] = models.JSONField(
        _("branding"),
        default=dict,
        help_text=_("Container for tenant branding."),
    )
    settings: models.JSONField[Dict[str, Any]] = models.JSONField(
        _("settings"),
        default=dict,
        help_text=_("Container for various tenant-specific settings."),
    )

    def __str__(self) -> str:
        return f"Configuration for {self.tenant.name}"

    class Meta:
        db_table: str = "tenant_configurations"
        verbose_name: str = _("tenant configuration")
        verbose_name_plural: str = _("tenant configurations")


class Role(TimestampedModel):
    """
    A set of permissions that can be assigned to users.
    Can be a system role (tenant=NULL) or a tenant-specific role.
    Corresponds to the 'roles' table.
    """

    tenant: models.ForeignKey[Optional[Tenant]] = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        related_name="roles",
        help_text=_("Null for global system roles."),
    )
    name: models.CharField[str] = models.CharField(_("name"), max_length=100)
    description: models.TextField[Optional[str]] = models.TextField(
        _("description"), blank=True, null=True
    )
    permissions: models.ManyToManyField[Permission, "RolePermission"] = (
        models.ManyToManyField(
            Permission, through="RolePermission", verbose_name=_("permissions")
        )
    )

    def __str__(self) -> str:
        if self.tenant:
            return f"{self.name} ({self.tenant.name})"
        return f"{self.name} (System Role)"

    class Meta:
        db_table: str = "roles"
        verbose_name: str = _("role")
        verbose_name_plural: str = _("roles")
        unique_together: list[list[str]] = [["tenant", "name"]]
        indexes: list[models.Index] = [
            models.Index(fields=["tenant"], name="idx_roles_tenant_id"),
        ]


class RolePermission(models.Model):
    """
    Intermediate table for the many-to-many relationship between Role and Permission.
    Corresponds to the 'role_permissions' table.
    """

    role: models.ForeignKey[Role] = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission: models.ForeignKey[Permission] = models.ForeignKey(
        Permission, on_delete=models.CASCADE
    )

    class Meta:
        db_table: str = "role_permissions"
        unique_together: list[list[str]] = [["role", "permission"]]


class UserTenantRole(models.Model):
    """
    Assigns a tenant-level role to a user (e.g., Tenant Administrator).
    Corresponds to the 'user_tenant_roles' table.
    """

    user: models.ForeignKey["User"] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("user")
    )
    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    role: models.ForeignKey[Role] = models.ForeignKey(
        Role, on_delete=models.PROTECT, verbose_name=_("role")
    )  # PROTECT = ON DELETE RESTRICT

    class Meta:
        db_table: str = "user_tenant_roles"
        verbose_name: str = _("user role in tenant")
        verbose_name_plural: str = _("user roles in tenant")
        unique_together: list[list[str]] = [["user", "tenant", "role"]]
        indexes: list[models.Index] = [
            models.Index(fields=["user"], name="idx_u_user_tenant_roles_id"),
            models.Index(fields=["tenant"], name="idx_t_user_tenant_roles_id"),
        ]


class Department(BaseAuditModel):
    """
    Represents a department within a tenant.
    Corresponds to the 'departments' table.
    """

    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    parent_department: models.ForeignKey[
        Optional["Department"], Optional["Department"]
    ] = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("parent department"),
    )
    name: models.CharField[str] = models.CharField(_("name"), max_length=255)
    description: models.TextField[Optional[str]] = models.TextField(
        _("description"), blank=True, null=True
    )
    contact_email: models.EmailField[Optional[str]] = models.EmailField(
        _("contact email"), blank=True, null=True
    )
    legal_name: models.CharField[Optional[str]] = models.CharField(
        _("legal name"), max_length=200, blank=True, null=True
    )

    def __str__(self) -> str:
        return self.name

    class Meta:
        db_table: str = "departments"
        verbose_name: str = _("department")
        verbose_name_plural: str = _("departments")
        unique_together: list[list[str]] = [["tenant", "name"]]
        indexes: list[models.Index] = [
            models.Index(fields=["tenant"], name="idx_departments_tenant_id"),
        ]


class UserDepartmentRole(models.Model):
    """
    Intermediate table assigning a user to a department with a specific role.
    Corresponds to the 'user_department_roles' table.
    """

    user: models.ForeignKey["User"] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("user")
    )
    department: models.ForeignKey[Department] = models.ForeignKey(
        Department, on_delete=models.CASCADE, verbose_name=_("department")
    )
    role: models.ForeignKey[Role] = models.ForeignKey(
        Role, on_delete=models.PROTECT, verbose_name=_("role")
    )

    class Meta:
        db_table: str = "user_department_roles"
        verbose_name: str = _("user department rol")
        verbose_name_plural: str = _("user department roles")
        unique_together: list[list[str]] = [
            ["user", "department", "role"],
        ]
        indexes: list[models.Index] = [
            models.Index(fields=["user"], name="idx_dept_users_user_id"),
            models.Index(fields=["department"], name="idx_dept_users_dept_id"),
        ]


class Invitation(TimestampedModel):
    """
    Stores invitations for new users to join an organization.
    Corresponds to the 'invitations' table.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        EXPIRED = "expired", _("Expired")
        REVOKED = "revoked", _("Revoked")

    tenant: models.ForeignKey[Tenant] = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("tenant")
    )
    department: models.ForeignKey[Department] = models.ForeignKey(
        Department, on_delete=models.CASCADE, verbose_name=_("organization")
    )
    invited_by_user: models.ForeignKey["User"] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("invited by")
    )
    role: models.ForeignKey[Role] = models.ForeignKey(
        Role, on_delete=models.CASCADE, verbose_name=_("assigned role")
    )
    invitee_email: models.EmailField[str] = models.EmailField(_("invitee email"))
    token: models.CharField[str] = models.CharField(
        _("token"), max_length=64, unique=True
    )
    status: models.CharField[str] = models.CharField(
        _("status"), max_length=50, choices=Status.choices, default=Status.PENDING
    )
    expires_at: models.DateTimeField = models.DateTimeField(_("expires at"))

    class Meta:
        db_table: str = "invitations"
        verbose_name: str = _("invitation")
        verbose_name_plural: str = _("invitations")
        indexes: list[models.Index] = [
            models.Index(fields=["tenant"], name="idx_invitations_tenant_id"),
            models.Index(fields=["department"], name="idx_invit_dep_id"),
        ]


class TenantAuditPolicy(models.Model):
    """
    Defines audit policies for a tenant.
    Corresponds to the 'tenant_audit_policies' table.
    """

    tenant: models.OneToOneField[Tenant] = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        primary_key=True,
        verbose_name=_("tenant"),
    )
    log_retention_days: models.IntegerField = models.IntegerField(
        _("log retention days"), default=365
    )
    require_log_signatures: models.BooleanField = models.BooleanField(
        _("require log signatures"), default=False
    )
    sensitive_tables: ArrayField[List[str]] = ArrayField(
        models.TextField(),
        verbose_name=_("sensitive tables"),
        default=list,
        blank=True,
        help_text=_("Tables that are logged in sensitive_access_logs."),
    )

    class Meta:
        db_table: str = "tenant_audit_policies"
        verbose_name: str = _("tenant audit policy")
        verbose_name_plural: str = _("tenant audit policies")
