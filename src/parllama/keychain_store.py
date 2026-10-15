"""Opt-in OS keychain storage for provider API keys.

Uses the ``keyring`` library, which selects the native backend per platform:
macOS Keychain, Windows Credential Manager, and Linux Secret Service
(gnome-keyring / KWallet). Where no backend exists (e.g. headless Linux) every
function degrades to a logged no-op so plaintext settings.json keeps working.
"""

from __future__ import annotations

import logging

import keyring
from keyring.backends.fail import Keyring as FailKeyring
from keyring.errors import KeyringError, PasswordDeleteError

logger = logging.getLogger(__name__)

SERVICE_NAME = "parllama"


def keychain_available() -> bool:
    """Return True when the platform offers a working keyring backend."""
    return not isinstance(keyring.get_keyring(), FailKeyring)


def keychain_get(account: str) -> str | None:
    """Return the stored secret for *account*, or None when missing or unavailable.

    Args:
        account: The keychain account name (the provider's env key name).
    """
    try:
        return keyring.get_password(SERVICE_NAME, account)
    except KeyringError as e:
        logger.warning("Could not read %s from the OS keychain: %s", account, e)
        return None


def keychain_set(account: str, value: str) -> bool:
    """Store *value* for *account*; True only when persisted.

    Args:
        account: The keychain account name (the provider's env key name).
        value: The secret to store.
    """
    try:
        keyring.set_password(SERVICE_NAME, account, value)
        return True
    except KeyringError as e:
        logger.warning("Could not store %s in the OS keychain: %s", account, e)
        return False


def keychain_delete(account: str) -> bool:
    """Remove *account*'s secret; True only when removed (or already absent).

    Args:
        account: The keychain account name (the provider's env key name).
    """
    try:
        keyring.delete_password(SERVICE_NAME, account)
        return True
    except PasswordDeleteError:
        return True  # already absent is the goal state
    except KeyringError as e:
        logger.warning("Could not remove %s from the OS keychain: %s", account, e)
        return False
