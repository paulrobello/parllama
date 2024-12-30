"""Manager for application secrets."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import orjson as json
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from orjson import JSONDecodeError
from textual.app import App

from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class SecretsManager(ParEventSystemBase):
    """
    Manager for application secrets.
    Uses PBKDF2 with HMAC-SHA256 to derive a key from a password,
    then uses AES-GCM encryption for storing secrets.
    Secrets are never stored in plain text, and only decrypted when accessed.
    """

    _key_secure: str | None = None
    """Encrypted current vault password"""
    _key: bytes | None = None
    """Decryption key derived from the password."""
    _salt: bytes
    """Used with password to derive the en/decryption key."""
    _secrets: dict[str, str]
    """Dict containing encrypted secrets."""
    _secrets_file: Path
    """JSON file containing encrypted secrets."""

    def __init__(self, secrets_file: str, **kwargs) -> None:
        """Initialize Manager and load vault."""
        super().__init__(**kwargs)
        self._secrets = {}
        self._salt = gen_salt()
        self._key_secure = None
        self._key = None
        self._secrets_file = Path(secrets_file)

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app and load existing sessions and prompts from storage"""
        super().set_app(app)
        self._load_secrets()
        env_key = os.environ.get("PARLLAMA_VAULT_KEY")
        if env_key:
            self.unlock(env_key, True)

    def _load_secrets(self) -> None:
        """Load secrets from the secrets file."""
        try:
            data = json.loads(self._secrets_file.read_bytes())
            self._salt = base64.b64decode(data.get("__salt__"))
            self._key_secure = data.get("__key__")
            self._secrets = data.get("secrets", {})
        except FileNotFoundError:
            self._secrets = {}
            self._salt = gen_salt()
            self._key_secure = None
        except JSONDecodeError as e:
            self.log_it(e)
            self.log_it("Invalid secrets file format", notify=True, severity="error")
            raise ValueError("Invalid secrets file format") from e

    def _save_secrets(self) -> None:
        """Saves secrets to the secrets file."""
        data = {
            "__salt__": base64.b64encode(self._salt).decode("utf-8"),
            "__key__": self._key_secure,
            "secrets": self._secrets,
        }
        self._secrets_file.write_bytes(json.dumps(data, str, json.OPT_INDENT_2))
        self.import_to_env(True)

    def _derive_key(self, password: str, alt_salt: bytes | None = None) -> bytes:
        """Derives a key from the given password and the stored salt."""
        return derive_key(password, alt_salt or self._salt)

    @property
    def locked(self) -> bool:
        """Checks if the secrets manager is locked."""
        return self._key is None

    def lock(self) -> None:
        """Locks the secrets manager."""
        self._key = None

    @property
    def has_password(self) -> bool:
        """Checks if a password is set."""
        return self._key_secure is not None

    def change_password(self, old_password: str, new_password: str, no_raise: bool = False) -> None:
        """Changes the password and re-encrypts existing secrets."""
        if not self.has_password:
            self.unlock(new_password)
            return

        if not self.verify_password(old_password):
            if no_raise:
                self.log_it("Invalid old password.", notify=True, severity="error")
                return
            raise ValueError("Invalid old password.")
        if new_password == old_password:
            return
        self.unlock(old_password)
        new_key: bytes = self._derive_key(new_password)
        self._key_secure = self._encrypt(new_password, new_key)

        encrypted_secrets = {}
        for key, value in self._secrets.items():
            encrypted_secrets[key] = self._encrypt(self._decrypt(value), new_key)
        self._secrets = encrypted_secrets
        self._key = new_key
        self._save_secrets()

    def verify_password(self, password: str) -> bool:
        """Verifies the given password. Returns True if vault password is not set."""
        try:
            if not self.has_password:
                return True
            return (
                self._decrypt(self._key_secure, self._derive_key(password)) == password  # type: ignore
            )
        except ValueError as e:
            self.log_it(e)
            return False

    def unlock(self, password: str, no_raise: bool = False) -> bool:
        """Unlock the vault or set initial vault password."""
        if not self.verify_password(password):
            self.lock()
            if no_raise:
                self.log_it("Invalid password.", notify=True, severity="error")
                return False
            raise ValueError("Invalid password.")
        self._key = self._derive_key(password)
        if self._key_secure is None:
            self._key_secure = self._encrypt(password, self._derive_key(password))
            self._save_secrets()
        return True

    def _encrypt(self, plaintext: str, alt_key: bytes | None = None) -> str:
        key: bytes | None = alt_key or self._key
        if key is None:
            raise ValueError("Password not set. Use unlock() before encrypting.")
        return encrypt(plaintext, key)

    def _decrypt(self, ciphertext: str, alt_key: bytes | None = None) -> str:
        """decrypt ciphertext with the provided key"""
        if self._key is None and alt_key is None:
            raise ValueError("Vault locked. Use unlock() before decrypting.")
        return decrypt(ciphertext, alt_key or self._key)  # type: ignore

    def add_secret(self, key: str, value: str, no_raise: bool = False):
        """Adds a new secret, encrypts it, and saves it to the file."""
        if not self._key:
            if no_raise:
                self.log_it("Password not set. Use unlock() before adding a secret.")
                return
            raise ValueError("Password not set. Use unlock() before adding a secret.")

        encrypted_value = self._encrypt(value)
        self._secrets[key] = encrypted_value
        self._save_secrets()

    def get_secret(self, key: str, default: str | None = None, no_raise: bool = False) -> str:
        """Decrypts and returns the secret associated with the given key."""
        if self.locked:
            if no_raise:
                return "Vault is locked"
            raise ValueError("Vault is locked")

        encrypted_value = self._secrets.get(key)
        if encrypted_value is None:
            if default is None:
                if no_raise:
                    return ""
                raise KeyError(f"No secret found for key: {key}")
            return default
        try:
            return self._decrypt(encrypted_value)
        except ValueError as e:
            if no_raise:
                return default or ""
            raise e

    def get_secret_with_pw(self, key: str, password: str, no_raise: bool = False) -> str:
        """Returns secret associated with the given key, using the provided password if vault is locked."""
        try:
            if self.locked:
                if not password:
                    if no_raise:
                        self.log_it(
                            "Password required to unlock the vault.",
                            notify=True,
                            severity="error",
                        )
                        return ""
                    raise ValueError("Password required to unlock the vault.")
                self.unlock(password)
            return self.get_secret(key)
        except ValueError as e:
            if no_raise:
                return ""
            raise e

    def encrypt_with_password(self, plaintext: str, password: str) -> str:
        """Encrypts plaintext with the provided password."""
        return self._encrypt(plaintext, self._derive_key(password))

    def decrypt_with_password(self, ciphertext: str, password: str) -> str:
        """Decrypts ciphertext with the provided password."""
        return self._decrypt(ciphertext, self._derive_key(password))

    def remove_secret(self, key: str, no_raise: bool = False) -> None:
        """Removes the secret associated with the given key and saves the changes."""
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
        else:
            if no_raise:
                self.log_it(f"No secret found for key: {key}", notify=True, severity="warning")
                return
            raise KeyError(f"No secret found for key: {key}")

    def clear(self) -> None:
        """Clear vault and remove password"""
        self._secrets.clear()
        self._salt = gen_salt()
        self._key_secure = None
        self.lock()
        self._save_secrets()
        self.log_it("Vault cleared and password removed.", notify=True)

    def import_to_env(self, no_raise: bool = False) -> None:
        """Imports secrets from the secrets file to the environment variables."""
        if self.locked:
            if no_raise:
                return
            raise ValueError("Vault is locked")
        for key, value in self._secrets.items():
            v = self._decrypt(value)
            if v:
                os.environ[key] = v

    @property
    def is_empty(self) -> bool:
        """Checks if the secrets manager is empty."""
        return len(self._secrets) == 0

    def __len__(self):
        """Returns the number of secrets stored."""
        return len(self._secrets)

    def __getitem__(self, key: str) -> str:
        """Allows access to secrets using square bracket notation."""
        return self.get_secret(key)

    def __setitem__(self, key: str, value: str) -> None:
        """Allows setting a secret using square bracket notation."""
        self.add_secret(key, value)

    def __delitem__(self, key: str) -> None:
        """Allows deletion of a secret using square bracket notation."""
        self.remove_secret(key)

    def __contains__(self, key: str) -> bool:
        """Allows checking if a key exists using the `in` keyword."""
        return key in self._secrets


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a key from the given password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(plaintext: str, key: bytes) -> str:
    """Encrypts plaintext with the given key bytes."""
    try:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
        return base64.b64encode(iv + encryptor.tag + encrypted).decode("utf-8")
    except (TypeError, ValueError, AttributeError) as e:
        raise ValueError(f"An error occurred: {e}") from e


def decrypt(ciphertext: str, key: bytes) -> str:
    """Decrypts ciphertext with the given key bytes."""
    try:
        decoded = base64.b64decode(ciphertext)
        iv, tag, encrypted = decoded[:12], decoded[12:28], decoded[28:]
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(encrypted) + decryptor.finalize()
        return plaintext.decode("utf-8")
    except (ValueError, TypeError, InvalidTag) as e:
        raise ValueError("Bad key or invalid / corrupted ciphertext.") from e


def encrypt_with_password(plaintext: str, password: str, salt: str | bytes) -> str:
    """Encrypts plaintext with the provided password."""
    return encrypt(
        plaintext,
        derive_key(password, base64.b64decode(salt) if isinstance(salt, str) else salt),
    )


def decrypt_with_password(ciphertext: str, password: str, salt: str | bytes) -> str:
    """Decrypts ciphertext with the provided password and salt."""
    return decrypt(
        ciphertext,
        derive_key(password, base64.b64decode(salt) if isinstance(salt, str) else salt),
    )


def gen_salt() -> bytes:
    """Generates random salt bytes."""
    return os.urandom(16)


secrets_manager = SecretsManager(settings.secrets_file)
