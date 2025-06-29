"""Test secrets manager"""

from __future__ import annotations

import json
import os.path
import unittest
from unittest.mock import mock_open
from unittest.mock import patch

from parllama.secrets_manager import SecretsManager


class TestSecretsManager(unittest.TestCase):
    """Test secrets manager"""

    def setUp(self):
        """Set up test environment"""
        self.secrets_file = "test-secrets.json"
        if os.path.exists(self.secrets_file):
            os.unlink(self.secrets_file)
        self.secrets_manager = SecretsManager(self.secrets_file)
        with patch("builtins.open", mock_open()):
            self.secrets_manager.unlock("test_password")

    def tearDown(self):
        """Cleanup test environment"""
        if os.path.exists(self.secrets_file):
            os.unlink(self.secrets_file)

    def test_encrypted_values(self):
        """Test that secrets are encrypted and decrypted correctly"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")
            handle = m()
            self.assertGreater(handle.write.call_count, 0)
            data_chunks = [call[0][0] for call in handle.write.call_args_list]
            data = json.loads("".join(data_chunks))
            self.assertNotEqual(data["secrets"]["test_key"], "test_value")

    def test_remove_secret(self):
        """Test that secrets can be removed correctly"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            self.assertIn("test_key", self.secrets_manager)
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.remove_secret("test_key")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

            handle = m()
            self.assertGreater(handle.write.call_count, 0)
            data_chunks = [call[0][0] for call in handle.write.call_args_list]
            data = json.loads("".join(data_chunks))
            self.assertNotIn("test_key", data["secrets"])

    def test_access_without_password(self):
        """Test that secrets cannot be accessed without a password"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            self.secrets_manager.lock()
            with self.assertRaises(ValueError):
                self.secrets_manager.get_secret("test_key")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

    def test_incorrect_password(self):
        """Test that secrets cannot be accessed with an incorrect password"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            self.assertEqual(len(self.secrets_manager), 1)
            with self.assertRaises(ValueError):
                self.secrets_manager.unlock("wrong_password")
            with self.assertRaises(ValueError):
                self.secrets_manager.get_secret("test_key")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

    def test_password_change(self):
        """Test that secrets can be accessed with the new password after changing it"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.change_password("test_password", "new_password")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")
        self.assertEqual(self.secrets_manager.get_secret("test_key"), "test_value")

    def test_password_change_with_bad_old_password(self):
        """Test that password can't be changed an incorrect old password"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.secrets_manager.change_password("wrong_password", "new_password")

    def test_verify_password(self):
        """Test that verify_password returns True with the correct password and False with an incorrect password"""
        with patch("builtins.open", mock_open()) as m:
            self.assertTrue(self.secrets_manager.verify_password("test_password"))
            self.assertFalse(self.secrets_manager.verify_password("wrong_password"))
            m.assert_not_called()

    def test_dunder_methods(self):
        """Test that secrets manager behaves as a dict"""
        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager.add_secret("test_key", "test_value")
            self.assertEqual(self.secrets_manager["test_key"], "test_value")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

        with patch("builtins.open", mock_open()) as m:
            self.secrets_manager["test_key"] = "new_value"
            self.assertEqual(self.secrets_manager["test_key"], "new_value")
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

        with patch("builtins.open", mock_open()) as m:
            del self.secrets_manager["test_key"]
            self.assertNotIn("test_key", self.secrets_manager)
            m.assert_called_once_with(self.secrets_file, "w", encoding="utf-8")

    def test_lock(self):
        """Test that secrets manager behaves as a dict"""
        assert not self.secrets_manager.locked
        self.secrets_manager.lock()
        assert self.secrets_manager.locked


if __name__ == "__main__":
    unittest.main()
