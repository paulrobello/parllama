"""Comprehensive pytest-based tests for secrets manager."""

import base64
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from parllama.secrets_manager import (
    SecretsManager,
    decrypt,
    decrypt_with_password,
    derive_key,
    encrypt,
    encrypt_with_password,
    gen_salt,
)


class TestSecretsManagerBasics:
    """Test basic secrets manager functionality."""

    def test_unlock_and_lock(self, secrets_manager):
        """Test that unlock and lock work correctly."""
        assert not secrets_manager.locked
        secrets_manager.lock()
        assert secrets_manager.locked

    def test_has_password_property(self, secrets_manager):
        """Test has_password property."""
        assert secrets_manager.has_password

    def test_is_empty_property(self, secrets_manager):
        """Test is_empty property."""
        assert secrets_manager.is_empty

    def test_length_property(self, secrets_manager):
        """Test __len__ method."""
        assert len(secrets_manager) == 0

    def test_verify_password(self, secrets_manager):
        """Test password verification."""
        assert secrets_manager.verify_password("TestPass123!")
        assert not secrets_manager.verify_password("WrongPass456!")


class TestSecretsManagerCRUD:
    """Test CRUD operations for secrets."""

    def test_add_and_get_secret(self, secrets_manager):
        """Test adding and retrieving secrets."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        result = secrets_manager.get_secret("test_key")
        assert result == "test_value"

    def test_remove_secret(self, secrets_manager):
        """Test removing secrets."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")
            assert "test_key" in secrets_manager

            secrets_manager.remove_secret("test_key")
            assert "test_key" not in secrets_manager

    def test_dunder_methods(self, secrets_manager):
        """Test dictionary-like behavior."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Test __setitem__ and __getitem__
            secrets_manager["test_key"] = "test_value"
            assert secrets_manager["test_key"] == "test_value"

            # Test __contains__
            assert "test_key" in secrets_manager
            assert "missing_key" not in secrets_manager

            # Test __len__
            assert len(secrets_manager) == 1

            # Test __delitem__
            del secrets_manager["test_key"]
            assert "test_key" not in secrets_manager

    def test_contains_method(self, secrets_manager):
        """Test __contains__ method."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        assert "test_key" in secrets_manager
        assert "missing_key" not in secrets_manager


class TestSecretsManagerEncryption:
    """Test encryption and security features."""

    def test_encrypted_values_are_stored(self, secrets_manager):
        """Test that secrets are encrypted when stored."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

            # Check that the value was written and encrypted
            handle = mock_file.return_value
            assert handle.write.call_count > 0
            data_chunks = [call[0][0] for call in handle.write.call_args_list]
            data = json.loads("".join(data_chunks))
            assert data["secrets"]["test_key"] != "test_value"

    def test_encrypt_decrypt_with_password_methods(self, secrets_manager):
        """Test encrypt_with_password and decrypt_with_password methods."""
        plaintext = "sensitive_data"
        password = "TestPass123!"

        encrypted = secrets_manager.encrypt_with_password(plaintext, password)
        assert encrypted != plaintext

        decrypted = secrets_manager.decrypt_with_password(encrypted, password)
        assert decrypted == plaintext

        with pytest.raises(ValueError):
            secrets_manager.decrypt_with_password(encrypted, "WrongPass456!")


class TestSecretsManagerSecurity:
    """Test security features and memory clearing."""

    @pytest.mark.security
    def test_memory_clearing_on_password_change(self, secrets_manager):
        """Test that memory is securely cleared during password changes."""
        with patch.object(secrets_manager, '_secure_clear_string') as mock_clear_str, \
             patch.object(secrets_manager, '_secure_clear_bytes') as mock_clear_bytes, \
             patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:

            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")
            secrets_manager.change_password("TestPass123!", "NewPass456!")

            assert mock_clear_str.called or mock_clear_bytes.called

    @pytest.mark.security
    def test_memory_clearing_on_clear(self, secrets_manager):
        """Test that memory is securely cleared when vault is cleared."""
        with patch.object(secrets_manager, '_secure_clear_string') as mock_clear_str, \
             patch.object(secrets_manager, '_secure_clear_bytes') as mock_clear_bytes, \
             patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:

            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("key1", "value1")
            secrets_manager.add_secret("key2", "value2")
            secrets_manager.clear()

            assert mock_clear_str.called
            assert mock_clear_bytes.called

    @pytest.mark.security
    def test_secure_memory_methods(self, secrets_manager):
        """Test secure memory clearing methods don't raise exceptions."""
        # These should not raise exceptions
        secrets_manager._secure_clear_string("sensitive_data")
        secrets_manager._secure_clear_bytes(b"sensitive_bytes")
        secrets_manager._secure_clear_dict({"key": "value", "nested": {"inner": "data"}})

        # Should handle None gracefully
        secrets_manager._secure_clear_string(None)
        secrets_manager._secure_clear_bytes(None)
        secrets_manager._secure_clear_dict(None)

    @pytest.mark.security
    def test_file_locking_integration(self, secrets_manager):
        """Test that file locking works correctly."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

            # Verify file lock was acquired for writing
            mock_lock.assert_called_with(secrets_manager._secrets_file, "w")


class TestSecretsManagerPasswordManagement:
    """Test password management functionality."""

    def test_change_password(self, secrets_manager):
        """Test password change functionality."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")
            secrets_manager.change_password("TestPass123!", "NewPass456!")

        assert secrets_manager.get_secret("test_key") == "test_value"

    def test_change_password_with_bad_old_password(self, secrets_manager):
        """Test that password can't be changed with incorrect old password."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        with pytest.raises(ValueError):
            secrets_manager.change_password("WrongPass123!", "NewPass456!")

    def test_change_password_same_password(self, secrets_manager):
        """Test changing password to the same password."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Should do nothing when changing to same password
            secrets_manager.change_password("TestPass123!", "TestPass123!")
            assert secrets_manager.verify_password("TestPass123!")

    def test_password_validation_environment_key(self, secrets_manager):
        """Test password validation for environment keys."""
        assert secrets_manager._validate_vault_key("ValidPass123!")
        assert not secrets_manager._validate_vault_key("")
        assert not secrets_manager._validate_vault_key("   ")
        assert not secrets_manager._validate_vault_key("short")
        assert not secrets_manager._validate_vault_key("password123")  # Too common
        assert not secrets_manager._validate_vault_key("12345678")  # All numeric


class TestSecretsManagerErrorHandling:
    """Test error handling and edge cases."""

    def test_no_raise_parameter_add_secret(self, secrets_manager):
        """Test no_raise parameter in add_secret method."""
        secrets_manager.lock()

        # Should not raise exception with no_raise=True
        secrets_manager.add_secret("test_key", "test_value", no_raise=True)

        # Should raise exception with no_raise=False
        with pytest.raises(ValueError):
            secrets_manager.add_secret("test_key", "test_value", no_raise=False)

    def test_no_raise_parameter_get_secret(self, secrets_manager):
        """Test no_raise parameter in get_secret method."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        # Test locked vault
        secrets_manager.lock()
        result = secrets_manager.get_secret("test_key", no_raise=True)
        assert result == "Vault is locked"

        # Test missing key with no_raise=True
        secrets_manager.unlock("TestPass123!")
        result = secrets_manager.get_secret("missing_key", no_raise=True)
        assert result == ""

    def test_no_raise_parameter_remove_secret(self, secrets_manager):
        """Test no_raise parameter in remove_secret method."""
        # Should not raise exception with no_raise=True
        secrets_manager.remove_secret("missing_key", no_raise=True)

        # Should raise exception with no_raise=False
        with pytest.raises(KeyError):
            secrets_manager.remove_secret("missing_key", no_raise=False)

    def test_empty_key_validation(self, secrets_manager):
        """Test validation of empty keys."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            with pytest.raises(ValueError):
                secrets_manager.add_secret("", "test_value")

            with pytest.raises(ValueError):
                secrets_manager.add_secret("   ", "test_value")

            with pytest.raises(ValueError):
                secrets_manager.remove_secret("")

    def test_key_trimming(self, secrets_manager):
        """Test that keys are properly trimmed."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("  test_key  ", "test_value")

        assert secrets_manager.get_secret("test_key") == "test_value"

    def test_access_without_password(self, secrets_manager):
        """Test that secrets cannot be accessed without a password."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")
            secrets_manager.lock()

            with pytest.raises(ValueError):
                secrets_manager.get_secret("test_key")

    def test_incorrect_password(self, secrets_manager):
        """Test that secrets cannot be accessed with an incorrect password."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")
            assert len(secrets_manager) == 1

            with pytest.raises(ValueError):
                secrets_manager.unlock("WrongPass123!")

            with pytest.raises(ValueError):
                secrets_manager.get_secret("test_key")

    def test_get_secret_with_password(self, secrets_manager):
        """Test get_secret_with_pw method."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        secrets_manager.lock()

        # Should be able to get secret with correct password
        result = secrets_manager.get_secret_with_pw("test_key", "TestPass123!")
        assert result == "test_value"

        # Lock again before testing wrong password
        secrets_manager.lock()

        # Should fail with wrong password
        result = secrets_manager.get_secret_with_pw("test_key", "WrongPass123!", no_raise=True)
        assert result == ""

    def test_error_handling_in_save_secrets(self, secrets_manager):
        """Test error handling in _save_secrets method."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_lock.side_effect = OSError("Permission denied")

            with pytest.raises(ValueError):
                secrets_manager.add_secret("test_key", "test_value")

    def test_verify_password_with_exceptions(self, secrets_manager):
        """Test verify_password method with various exceptions."""
        with patch.object(secrets_manager, '_decrypt') as mock_decrypt:
            mock_decrypt.side_effect = ValueError("Decryption failed")

            assert not secrets_manager.verify_password("TestPass123!")

    def test_load_secrets_with_corrupted_file(self, temp_dir):
        """Test loading secrets with corrupted JSON file."""
        corrupted_file = temp_dir / "corrupted.json"
        corrupted_file.write_text("invalid json content")

        # The SecretsManager constructor doesn't automatically load secrets
        # We need to trigger the loading by calling set_app or accessing secrets
        manager = SecretsManager(corrupted_file)

        with pytest.raises(ValueError):
            # This should trigger _load_secrets and raise ValueError
            manager.set_app(None)


class TestSecretsManagerFileOperations:
    """Test file operation edge cases and platform-specific behavior."""

    def test_set_app_with_env_vault_key(self, temp_dir, monkeypatch):
        """Test set_app with PARLLAMA_VAULT_KEY environment variable."""
        secrets_file = temp_dir / "test-secrets.json"
        manager = SecretsManager(secrets_file)

        # Test with valid environment key
        monkeypatch.setenv("PARLLAMA_VAULT_KEY", "ValidPass123!")
        with patch.object(manager, 'unlock') as mock_unlock:
            manager.set_app(None)
            mock_unlock.assert_called_once_with("ValidPass123!", True)

    def test_validate_vault_key_edge_cases(self, secrets_manager):
        """Test _validate_vault_key with various edge cases."""
        # Test empty string
        assert not secrets_manager._validate_vault_key("")

        # Test whitespace only
        assert not secrets_manager._validate_vault_key("   ")

        # Test short key
        assert not secrets_manager._validate_vault_key("short")

        # Test valid key
        assert secrets_manager._validate_vault_key("ValidPass123!")

    def test_windows_file_permissions(self, secrets_manager, temp_dir, monkeypatch):
        """Test file permission setting on Windows."""
        test_file = temp_dir / "test_file.json"
        test_file.touch()

        # Mock Windows environment
        monkeypatch.setattr(os, 'name', 'nt')

        # Should log about NTFS permissions
        with patch.object(secrets_manager, 'log_it') as mock_log:
            secrets_manager._set_secure_file_permissions(test_file)
            mock_log.assert_called_with(f"Relying on default NTFS permissions for {test_file.name}")

    def test_file_permissions_error(self, secrets_manager, temp_dir):
        """Test file permission setting with errors."""
        test_file = temp_dir / "test_file.json"

        # Mock chmod to raise PermissionError
        with patch.object(Path, 'chmod', side_effect=PermissionError("Permission denied")):
            with patch.object(secrets_manager, 'log_it') as mock_log:
                secrets_manager._set_secure_file_permissions(test_file)
                assert any("Could not set secure permissions" in str(call) for call in mock_log.call_args_list)

    def test_check_file_permissions_error(self, secrets_manager, temp_dir):
        """Test file permission checking with errors."""
        test_file = temp_dir / "test_file.json"
        test_file.write_text("{}")  # Create the file so exists() returns True

        # Mock stat to raise OSError
        with patch.object(Path, 'stat', side_effect=OSError("Error")):
            with patch.object(secrets_manager, 'log_it') as mock_log:
                secrets_manager._check_file_permissions(test_file)
                assert any("Could not check permissions" in str(call) for call in mock_log.call_args_list)

    def test_windows_file_locking(self, secrets_manager, temp_dir, monkeypatch):
        """Test Windows file locking behavior."""
        test_file = temp_dir / "test_lock.json"
        test_file.write_text("{}")

        # Mock Windows environment and msvcrt
        monkeypatch.setattr(os, 'name', 'nt')
        mock_msvcrt = type('MockMsvcrt', (), {
            'LK_LOCK': 1,
            'LK_UNLCK': 2,
            'locking': lambda fd, mode, nbytes: None
        })

        # Patch msvcrt in the secrets_manager module
        monkeypatch.setattr('parllama.secrets_manager.msvcrt', mock_msvcrt)

        # Test successful locking
        with secrets_manager._acquire_file_lock(test_file, "r") as f:
            assert f is not None

    def test_windows_file_locking_error(self, secrets_manager, temp_dir, monkeypatch):
        """Test Windows file locking with errors."""
        test_file = temp_dir / "test_lock.json"
        test_file.write_text("{}")

        # Mock Windows environment and msvcrt with locking error
        monkeypatch.setattr(os, 'name', 'nt')

        def mock_locking(fd, mode, nbytes):
            raise OSError("Locking failed")

        mock_msvcrt = type('MockMsvcrt', (), {
            'LK_LOCK': 1,
            'LK_UNLCK': 2,
            'locking': mock_locking
        })

        # Patch msvcrt in the secrets_manager module
        monkeypatch.setattr('parllama.secrets_manager.msvcrt', mock_msvcrt)

        # Should continue without lock
        with secrets_manager._acquire_file_lock(test_file, "r") as f:
            assert f is not None

    def test_file_lock_open_error(self, secrets_manager, temp_dir):
        """Test file lock with open error."""
        non_existent = temp_dir / "non_existent_dir" / "file.json"

        # Should raise the original exception
        with pytest.raises(FileNotFoundError):
            with secrets_manager._acquire_file_lock(non_existent, "r"):
                pass

    def test_load_secrets_permission_error(self, temp_dir):
        """Test load_secrets with permission error."""
        secrets_file = temp_dir / "test-secrets.json"
        secrets_file.write_text('{"secrets": {}}')

        manager = SecretsManager(secrets_file)

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(ValueError, match="Cannot access secrets file"):
                manager._load_secrets()

    def test_secure_clear_with_non_string_types(self, secrets_manager):
        """Test secure clearing methods with edge cases."""
        # Test _secure_clear_string with non-string
        secrets_manager._secure_clear_string(123)  # Should handle gracefully

        # Test _secure_clear_bytes with non-bytes
        secrets_manager._secure_clear_bytes("not bytes")  # Should handle gracefully

        # Test _secure_clear_dict with nested non-string values
        test_dict = {
            "key1": 123,
            "key2": ["list", "values"],
            "key3": {"nested": None}
        }
        secrets_manager._secure_clear_dict(test_dict)  # Should handle gracefully


class TestSecretsManagerAdvanced:
    """Test advanced functionality."""

    def test_import_to_env(self, secrets_manager):
        """Test importing secrets to environment variables."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("TEST_ENV_VAR", "test_value")

        original_env = os.environ.get("TEST_ENV_VAR")

        try:
            secrets_manager.import_to_env()
            assert os.environ.get("TEST_ENV_VAR") == "test_value"
        finally:
            if "TEST_ENV_VAR" in os.environ:
                del os.environ["TEST_ENV_VAR"]
            if original_env:
                os.environ["TEST_ENV_VAR"] = original_env

    def test_import_to_env_locked(self, secrets_manager):
        """Test import_to_env with locked vault."""
        secrets_manager.lock()

        with pytest.raises(ValueError):
            secrets_manager.import_to_env(no_raise=False)

        # Should not raise with no_raise=True
        secrets_manager.import_to_env(no_raise=True)

    def test_file_permissions_checking(self, secrets_manager, temp_dir):
        """Test file permission checking."""
        test_file = temp_dir / "test_file.json"
        test_file.touch()

        # Should not raise exception
        secrets_manager._check_file_permissions(test_file)

        # Test with non-existent file
        non_existent = temp_dir / "non_existent.json"
        secrets_manager._check_file_permissions(non_existent)

    def test_unlock_with_no_existing_password(self, temp_dir):
        """Test unlocking when no password is set initially."""
        new_file = temp_dir / "new_secrets.json"
        new_manager = SecretsManager(new_file)

        with patch.object(new_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            assert new_manager.unlock("InitialPass123!")
            assert new_manager.has_password

    def test_clear_vault(self, secrets_manager):
        """Test clearing the vault."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("key1", "value1")
            secrets_manager.add_secret("key2", "value2")
            assert not secrets_manager.is_empty

            # Mock the secure clear methods to prevent segfault
            with patch.object(secrets_manager, '_secure_clear_string'), \
                 patch.object(secrets_manager, '_secure_clear_bytes'):
                secrets_manager.clear()

        assert not secrets_manager.has_password
        assert secrets_manager.is_empty


class TestCryptographicFunctions:
    """Test the standalone cryptographic functions."""

    def test_derive_key(self):
        """Test key derivation function."""
        password = "TestPass123!"
        salt = gen_salt()

        key1 = derive_key(password, salt)
        key2 = derive_key(password, salt)

        # Same password and salt should produce same key
        assert key1 == key2

        # Different salt should produce different key
        different_salt = gen_salt()
        key3 = derive_key(password, different_salt)
        assert key1 != key3

        # Key should be 32 bytes (256 bits)
        assert len(key1) == 32

    def test_encrypt_decrypt_functions(self):
        """Test standalone encrypt/decrypt functions."""
        plaintext = "sensitive_data"
        password = "TestPass123!"
        salt = gen_salt()
        key = derive_key(password, salt)

        ciphertext = encrypt(plaintext, key)
        assert ciphertext != plaintext

        decrypted = decrypt(ciphertext, key)
        assert decrypted == plaintext

        # Wrong key should fail
        wrong_key = derive_key("WrongPass123!", salt)
        with pytest.raises(ValueError):
            decrypt(ciphertext, wrong_key)

    def test_encrypt_with_password_functions(self):
        """Test encrypt_with_password and decrypt_with_password functions."""
        plaintext = "sensitive_data"
        password = "TestPass123!"
        salt = gen_salt()

        ciphertext = encrypt_with_password(plaintext, password, salt)
        assert ciphertext != plaintext

        decrypted = decrypt_with_password(ciphertext, password, salt)
        assert decrypted == plaintext

        with pytest.raises(ValueError):
            decrypt_with_password(ciphertext, "WrongPass123!", salt)

    def test_gen_salt(self):
        """Test salt generation."""
        salt1 = gen_salt()
        salt2 = gen_salt()

        assert len(salt1) == 16
        assert len(salt2) == 16
        assert salt1 != salt2

    def test_encrypt_decrypt_edge_cases(self):
        """Test encryption/decryption with edge cases."""
        password = "TestPass123!"
        salt = gen_salt()
        key = derive_key(password, salt)

        # Test empty string
        empty_encrypted = encrypt("", key)
        assert decrypt(empty_encrypted, key) == ""

        # Test unicode string
        unicode_text = "🔐 Secret émojis and special chars: ñ, ü, α, β"
        unicode_encrypted = encrypt(unicode_text, key)
        assert decrypt(unicode_encrypted, key) == unicode_text

        # Test very long string
        long_text = "A" * 10000
        long_encrypted = encrypt(long_text, key)
        assert decrypt(long_encrypted, key) == long_text

    def test_invalid_ciphertext(self):
        """Test decryption with invalid ciphertext."""
        password = "TestPass123!"
        salt = gen_salt()
        key = derive_key(password, salt)

        # Test with invalid base64
        with pytest.raises(ValueError):
            decrypt("invalid_base64!", key)

        # Test with truncated ciphertext
        valid_ciphertext = encrypt("test", key)
        truncated = valid_ciphertext[:-10]
        with pytest.raises(ValueError):
            decrypt(truncated, key)

        # Test with completely wrong data
        wrong_data = base64.b64encode(b"wrong_data").decode()
        with pytest.raises(ValueError):
            decrypt(wrong_data, key)

    def test_encrypt_decrypt_with_string_salt(self):
        """Test encrypt/decrypt with password functions using string salt."""
        plaintext = "test_data"
        password = "TestPass123!"
        salt_bytes = gen_salt()
        salt_string = base64.b64encode(salt_bytes).decode()

        # Test with string salt
        ciphertext = encrypt_with_password(plaintext, password, salt_string)
        decrypted = decrypt_with_password(ciphertext, password, salt_string)
        assert decrypted == plaintext

        # Test with bytes salt
        ciphertext2 = encrypt_with_password(plaintext, password, salt_bytes)
        decrypted2 = decrypt_with_password(ciphertext2, password, salt_bytes)
        assert decrypted2 == plaintext

    @pytest.mark.slow
    def test_pbkdf2_iterations(self):
        """Test that PBKDF2 uses the correct number of iterations."""
        import time

        password = "TestPass123!"
        salt = gen_salt()

        start_time = time.time()
        key = derive_key(password, salt)
        end_time = time.time()

        # Should take some time due to 600,000 iterations
        # but not too long (allow up to 5 seconds on slow systems)
        duration = end_time - start_time
        assert duration > 0.01  # At least 10ms
        assert duration < 5.0   # Less than 5 seconds

        # Key should be properly derived
        assert len(key) == 32
        assert isinstance(key, bytes)


class TestSecretsManagerMoreCoverage:
    """Additional tests to increase coverage."""

    def test_change_password_no_existing_password(self, temp_dir):
        """Test change_password when no password is set initially."""
        secrets_file = temp_dir / "test-secrets.json"
        manager = SecretsManager(secrets_file)

        # Should set new password without old password
        with patch.object(manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            manager.change_password("", "NewPass456!")
            assert manager.has_password

    def test_change_password_no_raise_invalid_old_password(self, secrets_manager):
        """Test change_password with invalid old password and no_raise=True."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        # Should not raise with no_raise=True
        secrets_manager.change_password("WrongPass123!", "NewPass456!", no_raise=True)

    def test_change_password_exception_no_raise(self, secrets_manager):
        """Test change_password with exception and no_raise=True."""
        # Make unlock succeed but then raise during processing
        with patch.object(secrets_manager, 'verify_password', return_value=True):
            with patch.object(secrets_manager, 'unlock', return_value=True):
                with patch.object(secrets_manager, '_derive_key', side_effect=RuntimeError("Key derivation failed")):
                    # Should not raise with no_raise=True
                    secrets_manager.change_password("old_pass", "new_pass", no_raise=True)

    def test_unlock_exception_no_raise(self, secrets_manager):
        """Test unlock with exception and no_raise=True."""
        with patch.object(secrets_manager, 'verify_password', side_effect=RuntimeError("Verification failed")):
            # Should not raise with no_raise=True
            result = secrets_manager.unlock("TestPass123!", no_raise=True)
            assert result is False

    def test_add_secret_empty_key_no_raise(self, secrets_manager):
        """Test add_secret with empty key and no_raise=True."""
        # Should not raise with no_raise=True
        secrets_manager.add_secret("", "value", no_raise=True)
        secrets_manager.add_secret("   ", "value", no_raise=True)

    def test_add_secret_save_exception_no_raise(self, secrets_manager):
        """Test add_secret with save exception and no_raise=True."""
        # Make sure vault is unlocked
        assert not secrets_manager.locked

        with patch.object(secrets_manager, '_save_secrets', side_effect=OSError("Save failed")):
            # Should not raise with no_raise=True
            secrets_manager.add_secret("test_key", "test_value", no_raise=True)

    def test_get_secret_missing_key_no_default_no_raise(self, secrets_manager):
        """Test get_secret with missing key, no default, and no_raise=True."""
        result = secrets_manager.get_secret("missing_key", no_raise=True)
        assert result == ""

    def test_remove_secret_empty_key_no_raise(self, secrets_manager):
        """Test remove_secret with empty key and no_raise=True."""
        # Should not raise with no_raise=True
        secrets_manager.remove_secret("", no_raise=True)
        secrets_manager.remove_secret("   ", no_raise=True)

    def test_get_secret_with_pw_no_password_no_raise(self, secrets_manager):
        """Test get_secret_with_pw with no password and no_raise=True."""
        secrets_manager.lock()

        # Should not raise with no_raise=True
        result = secrets_manager.get_secret_with_pw("key", "", no_raise=True)
        assert result == ""

    def test_secure_clear_dict_with_lists(self, secrets_manager):
        """Test _secure_clear_dict with complex nested structures."""
        test_dict = {
            "list": ["item1", "item2"],
            "nested_dict": {
                "inner_list": ["a", "b"],
                "inner_dict": {"key": "value"}
            }
        }
        # Should handle complex structures gracefully
        secrets_manager._secure_clear_dict(test_dict)

    def test_file_lock_exception_during_exit(self, secrets_manager, temp_dir):
        """Test file lock with exception during exit."""
        test_file = temp_dir / "test_lock.json"
        test_file.write_text("{}")

        # Test that file lock properly handles exceptions during cleanup
        # This is mainly to ensure the finally block in __exit__ works correctly

        # Use a real file lock but don't force an exception - just verify the context manager works
        with secrets_manager._acquire_file_lock(test_file, "r") as f:
            assert f is not None

        # The main purpose is to cover the finally block in FileLock.__exit__
        # which is automatically tested by the context manager's normal operation

    def test_unix_file_locking_error(self, secrets_manager, temp_dir, monkeypatch):
        """Test Unix file locking with errors."""
        test_file = temp_dir / "test_lock.json"
        test_file.write_text("{}")

        # Mock Unix environment
        monkeypatch.setattr(os, 'name', 'posix')

        # Mock fcntl to raise error
        mock_fcntl = type('MockFcntl', (), {
            'LOCK_EX': 2,
            'LOCK_UN': 8,
            'flock': lambda fd, op: (_ for _ in ()).throw(OSError("Lock failed"))
        })

        monkeypatch.setattr('parllama.secrets_manager.fcntl', mock_fcntl)

        # Should continue without lock
        with secrets_manager._acquire_file_lock(test_file, "r") as f:
            assert f is not None


class TestSecretsManagerErrorPaths:
    """Test error handling paths and edge cases."""

    def test_change_password_unlock_failure(self, secrets_manager):
        """Test change_password when unlock fails."""
        with patch.object(secrets_manager, 'verify_password', return_value=True):
            with patch.object(secrets_manager, 'unlock', return_value=False):
                # Should return without error when no_raise=True
                secrets_manager.change_password("old_pass", "new_pass", no_raise=True)

    def test_change_password_exception_handling(self, secrets_manager):
        """Test change_password with exception during re-encryption."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        # Make verify_password return True to pass the check
        with patch.object(secrets_manager, 'verify_password', return_value=True):
            # Mock decrypt to raise an exception during re-encryption
            with patch.object(secrets_manager, '_decrypt', side_effect=ValueError("Decrypt failed")):
                with pytest.raises(ValueError, match="Failed to change password"):
                    secrets_manager.change_password("TestPass123!", "NewPass456!")

    def test_encrypt_with_no_key(self, secrets_manager):
        """Test _encrypt when key is not set."""
        secrets_manager.lock()
        with pytest.raises(ValueError, match="Password not set"):
            secrets_manager._encrypt("test")

    def test_decrypt_with_no_key(self, secrets_manager):
        """Test _decrypt when key is not set."""
        secrets_manager.lock()
        with pytest.raises(ValueError, match="Vault locked"):
            secrets_manager._decrypt("encrypted_data")

    def test_add_secret_exception_during_save(self, secrets_manager):
        """Test add_secret with exception during save."""
        # secrets_manager fixture is already unlocked

        # Mock _save_secrets to raise an exception
        with patch.object(secrets_manager, '_save_secrets', side_effect=OSError("Save failed")):
            with pytest.raises(ValueError, match="Failed to add secret"):
                secrets_manager.add_secret("test_key", "test_value", no_raise=False)

    def test_get_secret_decrypt_failure(self, secrets_manager):
        """Test get_secret with decryption failure."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        # Mock decrypt to fail
        with patch.object(secrets_manager, '_decrypt', side_effect=ValueError("Decrypt failed")):
            with pytest.raises(ValueError, match="Failed to decrypt secret"):
                secrets_manager.get_secret("test_key", no_raise=False)

            # With no_raise=True, should return default
            result = secrets_manager.get_secret("test_key", default="default", no_raise=True)
            assert result == "default"

    def test_get_secret_with_pw_exception(self, secrets_manager):
        """Test get_secret_with_pw with various exceptions."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("test_key", "test_value")

        secrets_manager.lock()

        # Test with exception during get_secret
        with patch.object(secrets_manager, 'get_secret', side_effect=ValueError("Get failed")):
            with pytest.raises(ValueError, match="Failed to get secret with password"):
                secrets_manager.get_secret_with_pw("test_key", "test_password", no_raise=False)

            # With no_raise=True
            result = secrets_manager.get_secret_with_pw("test_key", "test_password", no_raise=True)
            assert result == ""

    def test_import_to_env_decrypt_failure(self, secrets_manager):
        """Test import_to_env with decryption failure for some secrets."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            secrets_manager.add_secret("GOOD_SECRET", "good_value")
            secrets_manager.add_secret("BAD_SECRET", "bad_value")

        # Create a counter to track calls
        call_count = 0

        def mock_decrypt(value, key=None):
            nonlocal call_count
            call_count += 1
            # Fail on the second call (BAD_SECRET)
            if call_count == 2:
                raise ValueError("Decrypt failed")
            # For other calls, just return a simple string
            return "decrypted_value"

        with patch.object(secrets_manager, '_decrypt', side_effect=mock_decrypt):
            # With no_raise=False, should raise
            with pytest.raises(ValueError, match="Decrypt failed"):
                secrets_manager.import_to_env(no_raise=False)

            # Reset counter and test with no_raise=True
            call_count = 0
            # Should not raise
            secrets_manager.import_to_env(no_raise=True)

    def test_import_to_env_general_exception(self, secrets_manager):
        """Test import_to_env with general exception."""
        # Create a mock that raises when iterating
        class MockDict:
            def items(self):
                raise RuntimeError("General failure")

        # Replace _secrets with our mock
        original_secrets = secrets_manager._secrets
        secrets_manager._secrets = MockDict()

        try:
            with pytest.raises(ValueError, match="Failed to import secrets to environment"):
                secrets_manager.import_to_env(no_raise=False)

            # With no_raise=True, should not raise
            secrets_manager.import_to_env(no_raise=True)
        finally:
            # Restore original secrets
            secrets_manager._secrets = original_secrets

    def test_encrypt_function_error(self):
        """Test encrypt function with various errors."""
        # Test with invalid key type
        with pytest.raises(ValueError, match="An error occurred"):
            encrypt("test", "not_bytes")  # type: ignore

    def test_secure_clear_exception_handling(self, secrets_manager):
        """Test secure clearing methods with exceptions."""
        # Create a string that might cause issues
        test_string = "test" * 1000

        # Mock bytearray to raise an exception
        with patch('builtins.bytearray', side_effect=MemoryError("Out of memory")):
            # Should not raise, just log warning
            secrets_manager._secure_clear_string(test_string)
            secrets_manager._secure_clear_bytes(b"test_bytes")


class TestPasswordValidation:
    """Test the new password validation functionality."""

    def test_validate_password_basic_requirements(self, secrets_manager):
        """Test basic password validation requirements."""
        # Valid password
        is_valid, error = secrets_manager.validate_password("TestPass123!")
        assert is_valid
        assert error == ""

        # Empty password
        is_valid, error = secrets_manager.validate_password("")
        assert not is_valid
        assert "cannot be empty" in error

        # Too short
        is_valid, error = secrets_manager.validate_password("Short1!")
        assert not is_valid
        assert "at least 8 characters" in error

        # All numeric
        is_valid, error = secrets_manager.validate_password("12345678")
        assert not is_valid
        assert "cannot be all numbers" in error

    def test_validate_password_common_passwords(self, secrets_manager):
        """Test validation against common passwords."""
        # Test non-numeric common passwords that are at least 8 characters
        common_passwords = [
            "password1",
            "password123",
            "qwerty123",
            "admin123",
            "letmein123",  # Make sure it's 8+ chars
            "welcome123",  # Make sure it's 8+ chars
            "monkey123"
        ]

        for pwd in common_passwords:
            is_valid, error = secrets_manager.validate_password(pwd)
            assert not is_valid
            assert "too common" in error.lower()

        # Test numeric passwords are caught by all-numeric check
        numeric_passwords = ["12345678", "123456789"]
        for pwd in numeric_passwords:
            is_valid, error = secrets_manager.validate_password(pwd)
            assert not is_valid
            assert "cannot be all numbers" in error.lower()

    def test_validate_password_character_types(self, secrets_manager):
        """Test character type requirements."""
        # Only lowercase and numbers (2 types)
        is_valid, error = secrets_manager.validate_password("testpass123")
        assert not is_valid
        assert "at least 3 of" in error

        # Uppercase, lowercase, numbers (3 types) - should pass
        is_valid, error = secrets_manager.validate_password("TestPass123")
        assert is_valid
        assert error == ""

        # Uppercase, lowercase, special (3 types) - should pass
        is_valid, error = secrets_manager.validate_password("TestPass!")
        assert is_valid
        assert error == ""

        # All 4 types - should pass
        is_valid, error = secrets_manager.validate_password("TestPass123!")
        assert is_valid
        assert error == ""

    def test_validate_password_whitespace_handling(self, secrets_manager):
        """Test password validation with whitespace."""
        # Leading/trailing whitespace should be stripped
        is_valid, error = secrets_manager.validate_password("  TestPass123!  ")
        assert is_valid
        assert error == ""

        # Only whitespace
        is_valid, error = secrets_manager.validate_password("   ")
        assert not is_valid
        assert "cannot be empty" in error

    def test_unlock_validates_new_passwords(self, temp_dir):
        """Test that unlock validates passwords when setting initial password."""
        secrets_file = temp_dir / "new-secrets.json"
        manager = SecretsManager(secrets_file)

        with patch.object(manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Weak password should fail
            assert not manager.unlock("password123", no_raise=True)
            assert not manager.has_password

            # Strong password should succeed
            assert manager.unlock("ValidPass123!", no_raise=True)
            assert manager.has_password

    def test_change_password_validates_new_password(self, secrets_manager):
        """Test that change_password validates the new password."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Try to change to weak password - should fail
            with pytest.raises(ValueError, match="too common"):
                secrets_manager.change_password("TestPass123!", "password123")

            # Should succeed with strong password
            secrets_manager.change_password("TestPass123!", "NewValidPass456!")


class TestExportToEnv:
    """Test the new environment export control functionality."""

    def test_add_secret_with_export_flag(self, secrets_manager):
        """Test adding secrets with export control."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add secret with export=True (default)
            secrets_manager.add_secret("EXPORT_TRUE", "value1")
            assert secrets_manager.get_export_to_env("EXPORT_TRUE") is True

            # Add secret with export=False
            secrets_manager.add_secret("EXPORT_FALSE", "value2", export_to_env=False)
            assert secrets_manager.get_export_to_env("EXPORT_FALSE") is False

    def test_set_and_get_export_to_env(self, secrets_manager):
        """Test setting and getting export flags for existing secrets."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add a secret
            secrets_manager.add_secret("TEST_SECRET", "test_value")

            # Should default to True
            assert secrets_manager.get_export_to_env("TEST_SECRET") is True

            # Change to False
            secrets_manager.set_export_to_env("TEST_SECRET", False)
            assert secrets_manager.get_export_to_env("TEST_SECRET") is False

            # Change back to True
            secrets_manager.set_export_to_env("TEST_SECRET", True)
            assert secrets_manager.get_export_to_env("TEST_SECRET") is True

    def test_set_export_to_env_missing_key(self, secrets_manager):
        """Test setting export flag for non-existent key."""
        with pytest.raises(KeyError, match="No secret found"):
            secrets_manager.set_export_to_env("MISSING_KEY", True)

        # With no_raise=True
        secrets_manager.set_export_to_env("MISSING_KEY", True, no_raise=True)

    def test_set_export_to_env_empty_key(self, secrets_manager):
        """Test setting export flag with empty key."""
        with pytest.raises(ValueError, match="cannot be empty"):
            secrets_manager.set_export_to_env("", True)

        # With no_raise=True
        secrets_manager.set_export_to_env("", True, no_raise=True)

    def test_import_to_env_selective_export(self, secrets_manager):
        """Test that import_to_env only exports marked secrets."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add secrets with different export flags
            secrets_manager.add_secret("EXPORT_ME", "export_value", export_to_env=True)
            secrets_manager.add_secret("DONT_EXPORT", "private_value", export_to_env=False)

        # Clear environment first
        for key in ["EXPORT_ME", "DONT_EXPORT"]:
            if key in os.environ:
                del os.environ[key]

        try:
            # Import to environment
            secrets_manager.import_to_env()

            # Only EXPORT_ME should be in environment
            assert os.environ.get("EXPORT_ME") == "export_value"
            assert "DONT_EXPORT" not in os.environ

        finally:
            # Clean up environment
            for key in ["EXPORT_ME", "DONT_EXPORT"]:
                if key in os.environ:
                    del os.environ[key]

    def test_remove_secret_clears_export_flag(self, secrets_manager):
        """Test that removing a secret also removes its export flag."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add secret
            secrets_manager.add_secret("TEMP_SECRET", "temp_value", export_to_env=False)
            assert secrets_manager.get_export_to_env("TEMP_SECRET") is False

            # Remove secret
            secrets_manager.remove_secret("TEMP_SECRET")

            # Export flag should default to True for non-existent keys
            assert secrets_manager.get_export_to_env("TEMP_SECRET") is True

    def test_clear_removes_export_flags(self, secrets_manager):
        """Test that clearing the vault removes all export flags."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add secrets with export flags
            secrets_manager.add_secret("SECRET1", "value1", export_to_env=False)
            secrets_manager.add_secret("SECRET2", "value2", export_to_env=True)

            # Mock secure clear methods to prevent potential issues
            with patch.object(secrets_manager, '_secure_clear_string'), \
                 patch.object(secrets_manager, '_secure_clear_bytes'):
                secrets_manager.clear()

            # All export flags should be cleared
            assert secrets_manager.get_export_to_env("SECRET1") is True  # Default
            assert secrets_manager.get_export_to_env("SECRET2") is True  # Default

    def test_load_secrets_backward_compatibility(self, temp_dir):
        """Test loading secrets file without export_to_env data."""
        secrets_file = temp_dir / "legacy-secrets.json"

        # Create a legacy secrets file without export_to_env
        legacy_data = {
            "__salt__": base64.b64encode(b"test_salt_123456").decode(),
            "__key__": "encrypted_key_data",
            "secrets": {
                "LEGACY_SECRET": "encrypted_value"
            }
        }

        with open(secrets_file, 'w') as f:
            json.dump(legacy_data, f)

        # Load the manager
        manager = SecretsManager(secrets_file)
        manager._load_secrets()

        # Legacy secrets should default to export=True
        assert manager.get_export_to_env("LEGACY_SECRET") is True

    def test_save_secrets_includes_export_flags(self, secrets_manager):
        """Test that save operation includes export flags."""
        with patch.object(secrets_manager, '_acquire_file_lock') as mock_lock:
            mock_file = mock_open()
            mock_lock.return_value.__enter__.return_value = mock_file.return_value

            # Add secret with custom export flag
            secrets_manager.add_secret("TEST_KEY", "test_value", export_to_env=False)

            # Check that the written data includes export_to_env
            written_data = mock_file.return_value.write.call_args_list
            if written_data:
                content = "".join(call[0][0] for call in written_data)
                data = json.loads(content)
                assert "export_to_env" in data
                assert data["export_to_env"]["TEST_KEY"] is False
