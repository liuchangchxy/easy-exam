"""FPK deployments launch Compose directly, so the persisted DATA_DIR/.env is authoritative."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.infrastructure.db.repositories.ai_config_repository import (
    decrypt_secret,
    encrypt_secret,
)

SECRET_KEYS = ("EASYEXAM_SECRET_KEY", "SECRET_KEY")


class PersistedSecretTests(unittest.TestCase):
    def _clean_env(self):
        for name in SECRET_KEYS:
            os.environ.pop(name, None)

    def test_secret_is_loaded_from_data_dir_when_env_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                f"EASYEXAM_SECRET_KEY={'a' * 64}\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {"DATA_DIR": tmp}):
                self._clean_env()
                token = encrypt_secret("sk-persisted")
                self.assertTrue(token.startswith("enc:"))
                self.assertEqual(decrypt_secret(token), "sk-persisted")

    def test_secret_is_loaded_when_compose_passes_an_empty_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                f'EASYEXAM_SECRET_KEY="{"b" * 64}"\n', encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {"DATA_DIR": tmp, "EASYEXAM_SECRET_KEY": ""},
            ):
                token = encrypt_secret("sk-empty-env")
                self.assertEqual(decrypt_secret(token), "sk-empty-env")

    def test_environment_secret_takes_precedence_over_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                f"EASYEXAM_SECRET_KEY={'c' * 64}\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {"DATA_DIR": tmp, "EASYEXAM_SECRET_KEY": "d" * 64},
            ):
                token = encrypt_secret("sk-env")
                os.environ["EASYEXAM_SECRET_KEY"] = "c" * 64
                with self.assertRaises(ValueError):
                    decrypt_secret(token)

    def test_missing_secret_still_refuses_to_encrypt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DATA_DIR": tmp}):
                self._clean_env()
                with self.assertRaises(RuntimeError):
                    encrypt_secret("sk-missing")


if __name__ == "__main__":
    unittest.main()
