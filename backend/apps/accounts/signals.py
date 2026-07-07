"""Signal handlers for the accounts app.

Currently a placeholder. Phase 3 may hook a post_save handler on
``User`` to push user attributes to a search index, or on
``RefreshToken`` to enforce single-session policies.

The file is loaded eagerly by ``apps.accounts.apps.AccountsConfig.ready``,
which is why it exists even when empty.
"""
from __future__ import annotations
