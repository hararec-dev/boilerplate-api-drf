from typing import Optional, TYPE_CHECKING

from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
)
from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseAuditModel
from apps.tenancies.models import Tenant

from .managers import UserManager

if TYPE_CHECKING:
    from apps.tenancies.models import UserTenantRole


class User(AbstractBaseUser, BaseAuditModel, PermissionsMixin):
    """
    Custom user model. A user always belongs to a tenant.
    Corresponds to the 'users' table.
    """

    email: models.EmailField[str] = models.EmailField(
        _("email"), max_length=255, unique=True
    )
    first_name: models.CharField[str] = models.CharField(
        _("first name"), max_length=255, blank=True
    )
    last_name: models.CharField[str] = models.CharField(
        _("last name"), max_length=255, blank=True
    )
    avatar_url: models.URLField[Optional[str]] = models.URLField(
        _("avatar URL"), max_length=255, blank=True, null=True
    )
    mfa_secret: models.CharField[Optional[str]] = models.CharField(
        _("MFA secret"), max_length=100, blank=True, null=True
    )
    is_staff: models.BooleanField = models.BooleanField(
        _("staff"),
        default=False,
        help_text=_("Designates whether the user can log into the admin site."),
    )

    objects: UserManager = UserManager()

    USERNAME_FIELD: str = "email"
    REQUIRED_FIELDS: list[str] = []

    usertenantrole_set: "models.Manager[UserTenantRole]"

    class Meta:
        db_table: str = "users"
        verbose_name: str = _("user")
        verbose_name_plural: str = _("users")

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_tenants(self) -> QuerySet[Tenant]:
        """
        Returns a queryset of all tenants the user is associated with
        through the UserTenantRole model.
        It uses distinct() to avoid duplicates if a user has multiple
        roles in the same tenant.
        """
        tenant_ids: QuerySet[int] = self.usertenantrole_set.values_list(
            "tenant_id", flat=True
        )
        return Tenant.objects.filter(id__in=tenant_ids).distinct()
