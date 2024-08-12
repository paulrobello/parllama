"""Manager for application secrets."""

from __future__ import annotations

import os
import json
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.padding import PKCS7


from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class SecretsManager(ParEventSystemBase):
    """Manager for application settings."""

    _key: bytes | None = None
    _salt: bytes | None = None
    _secrets: dict[str, str]
    _secrets_file: str

    def __init__(self, secrets_file: str, **kwargs) -> None:
        """Initialize Manager."""
        super().__init__(**kwargs)
        self._secrets = {}
        self._key = None
        self._secrets_file = secrets_file
        self._load_secrets()

    def _load_secrets(self) -> None:
        """Load secrets from the secrets file."""
        try:
            with open(self._secrets_file, "r", encoding="utf-8") as file:
                data = json.load(file)
                self.salt = base64.b64decode(data.get("__salt__"))
                self._secrets = data.get("secrets", {})
        except FileNotFoundError:
            self._secrets = {}
            self.salt = os.urandom(16)  # Generate a new salt if file doesn't exist

    def _save_secrets(self) -> None:
        """Saves secrets to the secrets file."""
        data = {
            "__salt__": base64.b64encode(self.salt).decode("utf-8"),
            "secrets": self._secrets,
        }
        with open(self._secrets_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)

    def _derive_key(self, password: str) -> bytes:
        """Derives a key from the given password and the stored salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
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
        self.set_password("")

    def change_password(self, old_password: str, new_password: str) -> None:
        """Changes the password and re-encrypts the secrets."""
        if len(self) == 0:
            self.set_password(new_password)
            return

        if not self.verify_password(old_password):
            raise ValueError("Invalid old password.")

        new_key: bytes | None = self._derive_key(new_password)
        encrypted_secrets = {}
        for key, value in self._secrets.items():
            encrypted_secrets[key] = self._encrypt(self._decrypt(value), new_key)
        self._secrets = encrypted_secrets
        self._save_secrets()
        self.set_password(new_password)

    def verify_password(self, password: str) -> bool:
        """Verifies the given password."""
        if len(self) == 0:
            raise ValueError("Can't verify password without secrets.")
        try:
            values = list(self._secrets.values())
            self._decrypt(values[0], self._derive_key(password))
        except ValueError:
            return False
        return True

    def set_password(self, password: str) -> None:
        """Sets the password and derives the AES key."""
        if password:
            self._key = self._derive_key(password)
        else:
            self._key = None

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
        if self._key is None:
            raise ValueError("Password not set. Use set_password() before decrypting.")
        try:
            decoded = base64.b64decode(ciphertext)
            iv, encrypted = decoded[:16], decoded[16:]
            cipher = Cipher(
                algorithms.AES(alt_key or self._key),
                modes.CBC(iv),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            unpadder = PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(padded_data) + unpadder.finalize()
            return plaintext.decode("utf-8")
        except (ValueError, TypeError) as e:
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

    def get_secret(self, key: str) -> str:
        """Decrypts and returns the secret associated with the given key."""
        encrypted_value = self._secrets.get(key)
        if encrypted_value is None:
            raise KeyError(f"No secret found for key: {key}")
        return self._decrypt(encrypted_value)

    def remove_secret(self, key: str) -> None:
        """Removes the secret associated with the given key and saves the changes."""
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
        else:
            raise KeyError(f"No secret found for key: {key}")

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
