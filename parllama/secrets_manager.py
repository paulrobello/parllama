"""Manager for application secrets."""

from __future__ import annotations

import base64
import os
from typing import Optional
import simplejson as json

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.padding import PKCS7
from simplejson import JSONDecodeError

from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class SecretsManager(ParEventSystemBase):
    """
    Manager for application secrets.
    Uses PBKDF2 with HMAC-SHA256 to derive a key from a password,
    then uses AES-GCM encryption with PKCS7 padding for storing secrets.
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
    _secrets_file: str
    """JSON file containing encrypted secrets."""

    def __init__(self, secrets_file: str, **kwargs) -> None:
        """Initialize Manager and load vault."""
        super().__init__(**kwargs)
        self._secrets = {}
        self._salt = os.urandom(16)
        self._key_secure = None
        self._key = None
        self._secrets_file = secrets_file
        self._load_secrets()

    def _load_secrets(self) -> None:
        """Load secrets from the secrets file."""
        try:
            with open(self._secrets_file, "r", encoding="utf-8") as file:
                data = json.load(file)
                self._salt = base64.b64decode(data.get("__salt__"))
                self._key_secure = data.get("__key__")
                self._secrets = data.get("secrets", {})
        except FileNotFoundError:
            self._secrets = {}
            self._salt = os.urandom(16)
            self._key_secure = None
        except JSONDecodeError as e:
            self.log_it(e)
            raise ValueError("Invalid secrets file format") from e

    def _save_secrets(self) -> None:
        """Saves secrets to the secrets file."""
        data = {
            "__salt__": base64.b64encode(self._salt).decode("utf-8"),
            "__key__": self._key_secure,
            "secrets": self._secrets,
        }
        with open(self._secrets_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        self.import_to_env(True)

    def _derive_key(self, password: str) -> bytes:
        """Derives a key from the given password and the stored salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(password.encode("utf-8"))

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

    def change_password(self, old_password: str, new_password: str) -> None:
        """Changes the password and re-encrypts existing secrets."""
        if not self.has_password:
            self.unlock(new_password)
            return

        if not self.verify_password(old_password):
            raise ValueError("Invalid old password.")

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

    def unlock(self, password: str) -> None:
        """Unlock the vault or set initial vault password."""
        if not self.verify_password(password):
            self.lock()
            raise ValueError("Invalid password.")
        self._key = self._derive_key(password)
        if self._key_secure is None:
            self._key_secure = self._encrypt(password, self._derive_key(password))
            self._save_secrets()

    def _encrypt(self, plaintext: str, alt_key: bytes | None = None) -> str:
        key: bytes | None = alt_key or self._key
        if key is None:
            raise ValueError("Password not set. Use set_password() before encrypting.")

        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(iv + encrypted).decode("utf-8")

    def _decrypt(self, ciphertext: str, alt_key: bytes | None = None) -> str:
        if self._key is None and alt_key is None:
            raise ValueError("Password not set. Use set_password() before decrypting.")
        try:
            decoded = base64.b64decode(ciphertext)
            iv, encrypted = decoded[:16], decoded[16:]
            cipher = Cipher(
                algorithms.AES(alt_key or self._key),  # type: ignore
                modes.CBC(iv),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            unpadder = PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(padded_data) + unpadder.finalize()
            return plaintext.decode("utf-8")
        except (ValueError, TypeError) as e:
            self.log_it(e)
            raise ValueError("Bad password, invalid or corrupted secret.") from e

    def add_secret(self, key: str, value: str):
        """Adds a new secret, encrypts it, and saves it to the file."""
        if not self._key:
            raise ValueError(
                "Password not set. Use set_password() before adding a secret."
            )

        encrypted_value = self._encrypt(value)
        self._secrets[key] = encrypted_value
        self._save_secrets()

    def get_secret(
        self, key: str, default: Optional[str] = None, raise_error: bool = True
    ) -> str:
        """Decrypts and returns the secret associated with the given key."""
        if self.locked:
            if raise_error:
                raise ValueError("Vault is locked")
            return "Vault is locked"
        encrypted_value = self._secrets.get(key)
        if encrypted_value is None:
            if default is None:
                raise KeyError(f"No secret found for key: {key}")
            return default
        try:
            return self._decrypt(encrypted_value)
        except ValueError as e:
            if raise_error:
                raise e
            return default or ""

    def get_secret_with_pw(
        self, key: str, password: str, raise_error: bool = False
    ) -> str:
        """Returns secret associated with the given key, using the provided password if vault is locked."""
        try:
            if self.locked:
                if not password:
                    raise ValueError("Password required to unlock the vault.")
                self.unlock(password)
            return self.get_secret(key)
        except ValueError as e:
            if raise_error:
                raise e
            return ""

    def remove_secret(self, key: str) -> None:
        """Removes the secret associated with the given key and saves the changes."""
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
        else:
            raise KeyError(f"No secret found for key: {key}")

    def clear(self) -> None:
        """Clear vault and remove password"""
        self._secrets.clear()
        self._salt = os.urandom(16)
        self._key_secure = None
        self.lock()
        self._save_secrets()

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


secrets_manager = SecretsManager(settings.secrets_file)
