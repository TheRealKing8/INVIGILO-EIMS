"""INVIGILO core app — shared primitives.

This app owns:

* Base model classes (UUIDModel, TimestampedModel, SoftDeleteModel).
* Permission classes (HasPermission, IsRole, IsSuperAdmin).
* Scoped queryset mixin (role → row scope mapping from `03-use-cases.md`).
* Domain exception hierarchy and the DRF exception handler.
* Default pagination and filter sets.

No business logic lives here. The app is dependency-free aside from Django,
DRF, and the accounts app's user model (referenced by string).
"""
