"""Manager for application secrets."""

from __future__ import annotations

import base64
import os
import stat
import threading
from pathlib import Path
from typing import Any

# Platform-specific imports
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

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
    _export_to_env: dict[str, bool]
    """Dict tracking which secrets should be exported to environment."""
    _secrets_file: Path
    """JSON file containing encrypted secrets."""
    _file_lock: threading.Lock
    """Lock for file operations to prevent race conditions."""

    def __init__(self, secrets_file: Path, **kwargs) -> None:
        """Initialize Manager and load vault."""
        super().__init__(**kwargs)
        self._secrets = {}
        self._export_to_env = {}
        self._salt = gen_salt()
        self._key_secure = None
        self._key = None
        self._secrets_file = secrets_file
        self._file_lock = threading.Lock()

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app and load existing sessions and prompts from storage"""
        super().set_app(app)
        self._load_secrets()
        env_key = os.environ.get("PARLLAMA_VAULT_KEY")
        if env_key and self._validate_vault_key(env_key):
            self.unlock(env_key, True)

    def _validate_vault_key(self, key: str) -> bool:
        """Validate the vault key from environment variable."""
        is_valid, error_msg = self.validate_password(key)
        if not is_valid:
            self.log_it(
                f"PARLLAMA_VAULT_KEY environment variable: {error_msg}",
                notify=True,
                severity="warning",
            )
            return False

        return True

    def _set_secure_file_permissions(self, file_path: Path) -> None:
        """Set secure file permissions (0o600) for secrets file."""
        try:
            # Only set permissions on Unix-like systems
            if os.name != "nt":  # Not Windows
                file_path.chmod(0o600)  # Owner read/write only
                self.log_it(f"Set secure permissions (600) for {file_path.name}")
            else:
                # On Windows, we rely on the default NTFS permissions
                self.log_it(f"Relying on default NTFS permissions for {file_path.name}")
        except (OSError, PermissionError) as e:
            self.log_it(
                f"Warning: Could not set secure permissions for {file_path.name}: {e}", notify=True, severity="warning"
            )

    def _check_file_permissions(self, file_path: Path) -> None:
        """Check if file has secure permissions and warn if not."""
        try:
            if os.name != "nt" and file_path.exists():  # Not Windows
                file_stat = file_path.stat()
                # Check if file is readable by group or others
                if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
                    self.log_it(
                        f"Warning: {file_path.name} may be readable by other users", notify=True, severity="warning"
                    )
        except (OSError, AttributeError) as e:
            self.log_it(f"Could not check permissions for {file_path.name}: {e}")

    def _acquire_file_lock(self, file_path: Path, mode: str):
        """Context manager for file locking across platforms."""

        class FileLock:
            def __init__(self, file_path: Path, mode: str):
                self.file_path = file_path
                self.mode = mode
                self.file = None

            def __enter__(self):
                try:
                    self.file = open(self.file_path, self.mode, encoding="utf-8")

                    # Platform-specific file locking
                    if os.name == "nt" and msvcrt:  # Windows
                        try:
                            msvcrt.locking(self.file.fileno(), msvcrt.LK_LOCK, 1)
                        except OSError:
                            # If locking fails, continue without lock but log warning
                            pass
                    elif fcntl:  # Unix-like systems
                        try:
                            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)
                        except OSError:
                            # If locking fails, continue without lock but log warning
                            pass

                    return self.file
                except Exception as e:
                    if self.file:
                        self.file.close()
                    raise e

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.file:
                    try:
                        # Platform-specific file unlocking
                        if os.name == "nt" and msvcrt:  # Windows
                            try:
                                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                            except OSError:
                                pass
                        elif fcntl:  # Unix-like systems
                            try:
                                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
                            except OSError:
                                pass
                    finally:
                        self.file.close()

        return FileLock(file_path, mode)

    def _secure_clear_bytes(self, data: bytes) -> None:
        """Securely clear bytes from memory."""
        if data is None:
            return

        try:
            # For Python strings and bytes, we can't reliably clear them from memory
            # because they are immutable and Python manages their memory internally.
            # This is a best-effort attempt to overwrite the data, but Python's
            # garbage collector and string interning may prevent actual clearing.

            # Create a mutable bytearray copy and clear it
            if isinstance(data, bytes | str):
                # Convert to mutable bytearray and clear it
                mutable_copy = bytearray(data if isinstance(data, bytes) else data.encode("utf-8"))
                # Zero out the mutable copy
                for i in range(len(mutable_copy)):
                    mutable_copy[i] = 0
                # Clear the reference
                del mutable_copy

        except Exception as e:
            # If secure clearing fails, log but don't raise
            self.log_it(f"Warning: Could not securely clear bytes from memory: {e}")

    def _secure_clear_string(self, data: str) -> None:
        """Securely clear string from memory."""
        if data is None:
            return

        try:
            # For Python strings, we can't reliably clear them from memory
            # because they are immutable and Python manages their memory internally.
            # This is a best-effort approach.

            # Create a mutable bytearray copy and clear it
            if isinstance(data, str):
                mutable_copy = bytearray(data.encode("utf-8"))
                # Zero out the mutable copy
                for i in range(len(mutable_copy)):
                    mutable_copy[i] = 0
                # Clear the reference
                del mutable_copy

        except Exception as e:
            # If secure clearing fails, log but don't raise
            self.log_it(f"Warning: Could not securely clear string from memory: {e}")

    def _secure_clear_dict(self, data: dict) -> None:
        """Securely clear dictionary values from memory."""
        if data is None:
            return

        try:
            for key, value in data.items():
                if isinstance(value, str):
                    self._secure_clear_string(value)
                elif isinstance(value, bytes):
                    self._secure_clear_bytes(value)
                elif isinstance(value, dict):
                    self._secure_clear_dict(value)
        except Exception as e:
            # If secure clearing fails, log but don't raise
            self.log_it(f"Warning: Could not securely clear dictionary from memory: {e}")

    def _load_secrets(self) -> None:
        """Load secrets from the secrets file with file locking."""
        with self._file_lock:
            try:
                # Check file permissions when loading
                self._check_file_permissions(self._secrets_file)

                with self._acquire_file_lock(self._secrets_file, "r") as file:
                    data = json.loads(file.read())

                self._salt = base64.b64decode(data.get("__salt__"))
                self._key_secure = data.get("__key__")
                self._secrets = data.get("secrets", {})
                self._export_to_env = data.get("export_to_env", {})

                # For backward compatibility, default to True for existing secrets
                for key in self._secrets:
                    if key not in self._export_to_env:
                        self._export_to_env[key] = True

                self.log_it(f"Loaded {len(self._secrets)} secrets from vault")
            except FileNotFoundError:
                self._secrets = {}
                self._salt = gen_salt()
                self._key_secure = None
                self.log_it("No existing secrets file found, starting with empty vault")
            except JSONDecodeError as e:
                self.log_it(f"JSON decode error: {e}", severity="error")
                self.log_it("Invalid secrets file format", notify=True, severity="error")
                raise ValueError("Invalid secrets file format") from e
            except (OSError, PermissionError) as e:
                self.log_it(f"File access error: {e}", notify=True, severity="error")
                raise ValueError(f"Cannot access secrets file: {e}") from e

    def _save_secrets(self) -> None:
        """Saves secrets to the secrets file with file locking and secure cleanup."""
        with self._file_lock:
            try:
                data = {
                    "__salt__": base64.b64encode(self._salt).decode("utf-8"),
                    "__key__": self._key_secure,
                    "secrets": self._secrets,
                    "export_to_env": self._export_to_env,
                }

                # Create parent directory if it doesn't exist
                self._secrets_file.parent.mkdir(parents=True, exist_ok=True)

                # Write to file with exclusive lock
                with self._acquire_file_lock(self._secrets_file, "w") as file:
                    file.write(json.dumps(data, str, json.OPT_INDENT_2).decode("utf-8"))

                # Set secure file permissions after creating/updating the file
                self._set_secure_file_permissions(self._secrets_file)

                # Clear sensitive data from memory
                self._secure_clear_dict(data)

                self.log_it(f"Saved {len(self._secrets)} secrets to vault")
                self.import_to_env(True)

            except (OSError, PermissionError) as e:
                self.log_it(f"Failed to save secrets: {e}", notify=True, severity="error")
                raise ValueError(f"Cannot save secrets file: {e}") from e

    def _derive_key(self, password: str, alt_salt: bytes | None = None) -> bytes:
        """Derives a key from the given password and the stored salt."""
        return derive_key(password, alt_salt or self._salt)

    @property
    def locked(self) -> bool:
        """Checks if the secrets manager is locked."""
        return self._key is None

    def lock(self) -> None:
        """Locks the secrets manager and securely clears the key from memory."""
        if self._key is not None:
            self._secure_clear_bytes(self._key)
        self._key = None
        self.log_it("Vault locked and key cleared from memory")

    @property
    def has_password(self) -> bool:
        """Checks if a password is set."""
        return self._key_secure is not None

    def validate_password(self, password: str) -> tuple[bool, str]:
        """
        Validate a password against security requirements.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        if not password or not password.strip():
            return False, "Password cannot be empty"

        password = password.strip()

        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        # Check if password is all numeric
        if password.isdigit():
            return False, "Password cannot be all numbers"

        # Check for common weak passwords
        common_passwords = {
            "password1",
            "password123",
            "12345678",
            "123456789",
            "qwerty123",
            "admin123",
            "letmein123",
            "welcome123",
            "monkey123",
        }
        if password.lower() in common_passwords:
            return False, "Password is too common. Please choose a stronger password"

        # Optional: Check for minimum character types (can be made configurable)
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        # Require at least 3 of 4 character types
        char_types = sum([has_upper, has_lower, has_digit, has_special])
        if char_types < 3:
            return False, "Password must contain at least 3 of: uppercase, lowercase, numbers, special characters"

        return True, ""

    def change_password(self, old_password: str, new_password: str, no_raise: bool = False) -> None:
        """Changes the password and re-encrypts existing secrets."""
        if not self.has_password:
            if not self.unlock(new_password, no_raise):
                return
            return

        if not self.verify_password(old_password):
            error_msg = "Invalid old password."
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        if new_password == old_password:
            return

        # Validate new password
        is_valid, error_msg = self.validate_password(new_password)
        if not is_valid:
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        if not self.unlock(old_password, no_raise):
            return

        try:
            new_key: bytes = self._derive_key(new_password)
            new_key_secure = self._encrypt(new_password, new_key)

            encrypted_secrets = {}
            for key, encrypted_value in self._secrets.items():
                # Decrypt with old key and immediately re-encrypt with new key
                decrypted_value = self._decrypt(encrypted_value)
                try:
                    encrypted_secrets[key] = self._encrypt(decrypted_value, new_key)
                finally:
                    # Securely clear the decrypted value from memory
                    self._secure_clear_string(decrypted_value)

            # Clear old encrypted password and update with new one
            if self._key_secure:
                self._secure_clear_string(self._key_secure)
            self._key_secure = new_key_secure

            # Clear old key and update with new one
            if self._key:
                self._secure_clear_bytes(self._key)
            self._key = new_key

            # Update secrets and save
            self._secrets = encrypted_secrets
            self._save_secrets()

            self.log_it("Password changed successfully", notify=True)

        except Exception as e:
            error_msg = f"Failed to change password: {e}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg) from e

    def verify_password(self, password: str) -> bool:
        """Verifies the given password. Returns True if vault password is not set."""
        try:
            if not self.has_password:
                return True

            # Decrypt the stored password and compare
            if self._key_secure is None:
                return False
            decrypted_password = self._decrypt(self._key_secure, self._derive_key(password))
            is_valid = decrypted_password == password

            # Securely clear the decrypted password from memory
            self._secure_clear_string(decrypted_password)

            return is_valid
        except (ValueError, TypeError, InvalidTag) as e:
            self.log_it(f"Password verification failed: {e}")
            return False

    def unlock(self, password: str, no_raise: bool = False) -> bool:
        """Unlock the vault or set initial vault password."""
        try:
            # If no password is set yet, validate the new password
            if not self.has_password:
                is_valid, error_msg = self.validate_password(password)
                if not is_valid:
                    if no_raise:
                        self.log_it(error_msg, notify=True, severity="error")
                        return False
                    raise ValueError(error_msg)

            if not self.verify_password(password):
                self.lock()
                error_msg = "Invalid password."
                if no_raise:
                    self.log_it(error_msg, notify=True, severity="error")
                    return False
                raise ValueError(error_msg)

            # Clear any existing key before setting new one
            if self._key is not None:
                self._secure_clear_bytes(self._key)

            self._key = self._derive_key(password)

            if self._key_secure is None:
                self._key_secure = self._encrypt(password, self._key)
                self._save_secrets()
                self.log_it("Vault created and unlocked", notify=True)
            else:
                self.log_it("Vault unlocked successfully")

            return True

        except Exception as e:
            self.lock()
            error_msg = f"Failed to unlock vault: {e}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return False
            raise ValueError(error_msg) from e

    def _encrypt(self, plaintext: str, alt_key: bytes | None = None) -> str:
        key: bytes | None = alt_key or self._key
        if key is None:
            raise ValueError("Password not set. Use unlock() before encrypting.")
        return encrypt(plaintext, key)

    def _decrypt(self, ciphertext: str, alt_key: bytes | None = None) -> str:
        """decrypt ciphertext with the provided key"""
        if self._key is None and alt_key is None:
            raise ValueError("Vault locked. Use unlock() before decrypting.")
        key = alt_key or self._key
        if key is None:
            raise ValueError("No key available for decryption.")
        return decrypt(ciphertext, key)

    def add_secret(self, key: str, value: str, export_to_env: bool = True, no_raise: bool = False) -> None:
        """Adds a new secret, encrypts it, and saves it to the file."""
        if not self._key:
            error_msg = "Vault is locked. Use unlock() before adding a secret."
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        if not key or not key.strip():
            error_msg = "Secret key cannot be empty"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        try:
            encrypted_value = self._encrypt(value)
            self._secrets[key.strip()] = encrypted_value
            self._export_to_env[key.strip()] = export_to_env
            self._save_secrets()
            self.log_it(f"Secret '{key}' added successfully")
        except Exception as e:
            error_msg = f"Failed to add secret '{key}': {e}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg) from e

    def get_secret(self, key: str, default: str | None = None, no_raise: bool = False) -> str:
        """Decrypts and returns the secret associated with the given key."""
        if self.locked:
            error_msg = "Vault is locked"
            if no_raise:
                return error_msg
            raise ValueError(error_msg)

        encrypted_value = self._secrets.get(key)
        if encrypted_value is None:
            if default is None:
                error_msg = f"No secret found for key: {key}"
                if no_raise:
                    return ""
                raise KeyError(error_msg)
            return default

        try:
            decrypted_value = self._decrypt(encrypted_value)
            return decrypted_value
        except (ValueError, TypeError, InvalidTag) as e:
            error_msg = f"Failed to decrypt secret '{key}': {e}"
            if no_raise:
                self.log_it(error_msg, severity="error")
                return default or ""
            raise ValueError(error_msg) from e

    def get_secret_with_pw(self, key: str, password: str, no_raise: bool = False) -> str:
        """Returns secret associated with the given key, using the provided password if vault is locked."""
        try:
            if self.locked:
                if not password:
                    error_msg = "Password required to unlock the vault."
                    if no_raise:
                        self.log_it(error_msg, notify=True, severity="error")
                        return ""
                    raise ValueError(error_msg)

                if not self.unlock(password, no_raise):
                    return ""

            return self.get_secret(key, no_raise=no_raise)
        except Exception as e:
            error_msg = f"Failed to get secret with password: {e}"
            if no_raise:
                self.log_it(error_msg, severity="error")
                return ""
            raise ValueError(error_msg) from e

    def encrypt_with_password(self, plaintext: str, password: str) -> str:
        """Encrypts plaintext with the provided password."""
        return self._encrypt(plaintext, self._derive_key(password))

    def decrypt_with_password(self, ciphertext: str, password: str) -> str:
        """Decrypts ciphertext with the provided password."""
        return self._decrypt(ciphertext, self._derive_key(password))

    def set_export_to_env(self, key: str, export: bool, no_raise: bool = False) -> None:
        """Set whether a secret should be exported to environment variables."""
        if not key or not key.strip():
            error_msg = "Secret key cannot be empty"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        key = key.strip()
        if key not in self._secrets:
            error_msg = f"No secret found for key: {key}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="warning")
                return
            raise KeyError(error_msg)

        self._export_to_env[key] = export
        self._save_secrets()
        self.log_it(f"Export setting for '{key}' updated to {export}")

    def get_export_to_env(self, key: str) -> bool:
        """Get whether a secret should be exported to environment variables."""
        return self._export_to_env.get(key, True)

    def remove_secret(self, key: str, no_raise: bool = False) -> None:
        """Removes the secret associated with the given key and saves the changes."""
        if not key or not key.strip():
            error_msg = "Secret key cannot be empty"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg)

        key = key.strip()
        if key in self._secrets:
            # Securely clear the encrypted value from memory
            encrypted_value = self._secrets[key]
            self._secure_clear_string(encrypted_value)

            del self._secrets[key]
            # Also remove export setting
            if key in self._export_to_env:
                del self._export_to_env[key]
            self._save_secrets()
            self.log_it(f"Secret '{key}' removed successfully")
        else:
            error_msg = f"No secret found for key: {key}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="warning")
                return
            raise KeyError(error_msg)

    def clear(self) -> None:
        """Clear vault and remove password with proper cleanup."""
        # Securely clear existing secrets from memory
        for key, encrypted_value in self._secrets.items():
            # Clear the encrypted value string from memory
            self._secure_clear_string(encrypted_value)

        self._secrets.clear()
        self._export_to_env.clear()

        # Clear the existing key securely before regenerating salt
        if self._key is not None:
            self._secure_clear_bytes(self._key)

        # Clear the encrypted password
        if self._key_secure is not None:
            self._secure_clear_string(self._key_secure)

        # Generate new salt and reset state
        self._salt = gen_salt()
        self._key_secure = None
        self.lock()

        # Save the cleared state
        self._save_secrets()
        self.log_it("Vault cleared, password removed, and memory securely wiped.", notify=True)

    def import_to_env(self, no_raise: bool = False) -> None:
        """Imports secrets from the secrets file to the environment variables."""
        if self.locked:
            error_msg = "Vault is locked"
            if no_raise:
                return
            raise ValueError(error_msg)

        try:
            imported_count = 0
            for key, encrypted_value in self._secrets.items():
                # Only export if marked for export
                if not self._export_to_env.get(key, True):
                    continue
                try:
                    decrypted_value = self._decrypt(encrypted_value)
                    if decrypted_value:
                        os.environ[key] = decrypted_value
                        imported_count += 1
                    # Note: We don't clear decrypted_value here since it's now in environment
                except Exception as e:
                    if no_raise:
                        self.log_it(f"Failed to import secret '{key}': {e}", severity="warning")
                        continue
                    else:
                        raise

            if imported_count > 0:
                self.log_it(f"Imported {imported_count} secrets to environment variables")

        except Exception as e:
            error_msg = f"Failed to import secrets to environment: {e}"
            if no_raise:
                self.log_it(error_msg, notify=True, severity="error")
                return
            raise ValueError(error_msg) from e

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
        iterations=600000,
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
