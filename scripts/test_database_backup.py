"""Backup tooling checks use real GPG and a mocked local Docker boundary."""
import os
from pathlib import Path
import secrets
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import database_backup as backup


class BackupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory(prefix="reseller-backup-test-")
        self.addCleanup(self.private.cleanup)
        self.root = Path(self.private.name)
        self.key = self.root / "passphrase"
        self.key.write_text(secrets.token_hex(32) + "\n")
        self.key.chmod(0o600)
        self.archive = self.root / "snapshot.gpg"
        self.fixture = b"PGDMP" + bytes(range(256)) * 8

    def make_archive(self):
        def dump(container, arguments, **kwargs):
            self.assertEqual(container, "local-drill")
            self.assertEqual(arguments[0], "pg_dump")
            self.assertIn("--format=custom", arguments)
            kwargs["output_file"].write(self.fixture)
        with patch.object(backup, "_docker", side_effect=dump):
            return self.do_backup()

    def do_backup(self, **overrides):
        options = dict(container="local-drill", user="postgres", database="source",
                       output=self.archive, passphrase_file=self.key)
        options.update(overrides)
        return backup.backup_database(**options)

    def do_restore(self, **overrides):
        options = dict(container="local-drill", user="postgres", database="target",
                       archive=self.archive, passphrase_file=self.key, confirm_empty_target="target")
        options.update(overrides)
        return backup.restore_database(**options)

    def test_existing_output_is_never_overwritten(self):
        self.archive.write_bytes(b"keep-existing-backup")
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError):
                self.do_backup()
            database.assert_not_called()
        self.assertEqual(self.archive.read_bytes(), b"keep-existing-backup")

    def test_group_or_world_readable_key_is_rejected(self):
        for mode in (0o640, 0o604, 0o644):
            with self.subTest(mode=oct(mode)):
                self.key.chmod(mode)
                with patch.object(backup, "_docker") as database:
                    with self.assertRaises(backup.BackupError):
                        self.do_backup()
                    database.assert_not_called()
                self.assertFalse(self.archive.exists())

    def test_symlink_key_is_rejected(self):
        link = self.root / "key-link"
        link.symlink_to(self.key)
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError):
                self.do_backup(passphrase_file=link)
            database.assert_not_called()
        self.assertFalse(self.archive.exists())

    def test_empty_key_is_rejected(self):
        self.key.write_bytes(b"")
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError):
                self.do_backup()
            database.assert_not_called()
        self.assertFalse(self.archive.exists())

    def test_whitespace_or_multiline_keys_are_rejected_before_database_access(self):
        for value in (b" \t\n", b"first\nsecond\n", b"first\n\n"):
            with self.subTest(value=value):
                self.key.write_bytes(value)
                with patch.object(backup, "_docker") as database:
                    with self.assertRaises(backup.BackupError):
                        self.do_backup()
                    database.assert_not_called()

    def test_restore_requires_matching_explicit_target_confirmation(self):
        self.archive.write_bytes(b"not-a-backup")
        for confirmation in (None, "", "another_database"):
            with self.subTest(confirmation=confirmation), patch.object(backup, "_docker") as database:
                with self.assertRaises(backup.BackupError):
                    self.do_restore(confirm_empty_target=confirmation)
                database.assert_not_called()

    def test_encrypted_roundtrip_preserves_bytes_and_uses_transactional_restore(self):
        self.make_archive()
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode), 0o600)
        self.assertNotIn(self.fixture, self.archive.read_bytes())
        operations = []

        def restore(container, arguments, **kwargs):
            operations.append(arguments)
            if arguments[0] == "psql":
                self.assertTrue(kwargs["capture"])
                return b"empty\n"
            self.assertEqual(arguments[0], "pg_restore")
            # A child process consumes the inherited OS descriptor, not Python's
            # buffered reader. This detects read-ahead followed by an in-buffer seek.
            self.assertEqual(os.read(kwargs["input_file"].fileno(), len(self.fixture) + 1), self.fixture)
            self.assertTrue({"--exit-on-error", "--single-transaction", "--no-owner", "--no-acl"}.issubset(arguments))
            self.assertNotIn("--clean", arguments)

        with patch.object(backup, "_docker", side_effect=restore):
            self.do_restore()
        self.assertEqual([op[0] for op in operations], ["psql", "pg_restore"])
        self.assertFalse(list(self.root.glob(".pg-backup-*")))

    def test_wrong_key_fails_before_any_database_request(self):
        self.make_archive()
        wrong = self.root / "wrong-key"
        wrong.write_text(secrets.token_hex(32))
        wrong.chmod(0o600)
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError) as failure:
                self.do_restore(passphrase_file=wrong)
            database.assert_not_called()
        self.assertIn("integrity", str(failure.exception))
        self.assertNotIn(wrong.read_text(), str(failure.exception))

    def test_corrupt_archive_is_rejected_before_any_database_request(self):
        self.make_archive()
        encrypted = bytearray(self.archive.read_bytes())
        encrypted[-12] ^= 0x80
        self.archive.write_bytes(encrypted)
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError):
                self.do_restore()
            database.assert_not_called()

    def test_non_postgres_plaintext_is_rejected_before_database_request(self):
        self.fixture = b"untrusted arbitrary plaintext"
        self.make_archive()
        with patch.object(backup, "_docker") as database:
            with self.assertRaises(backup.BackupError):
                self.do_restore()
            database.assert_not_called()

    def test_nonempty_target_is_never_restored(self):
        self.make_archive()
        with patch.object(backup, "_docker", return_value=b"nonempty\n") as database:
            with self.assertRaises(backup.BackupError):
                self.do_restore()
        self.assertEqual(database.call_count, 1)
        self.assertEqual(database.call_args.args[1][0], "psql")

    def test_unrecognized_empty_check_response_fails_closed(self):
        self.make_archive()
        for result in (b"", b"t\n", b"empty\nnonempty\n"):
            with self.subTest(result=result), patch.object(backup, "_docker", return_value=result) as database:
                with self.assertRaises(backup.BackupError):
                    self.do_restore()
                self.assertEqual(database.call_count, 1)

    def test_failed_dump_does_not_publish_or_retain_plaintext(self):
        def fail(container, arguments, **kwargs):
            kwargs["output_file"].write(self.fixture)
            raise backup.BackupError("Database dump failed")
        with patch.object(backup, "_docker", side_effect=fail):
            with self.assertRaises(backup.BackupError):
                self.do_backup()
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.root.glob(".pg-backup-*")))

    def test_restore_failure_cleans_private_plaintext(self):
        self.make_archive()
        original = backup._gpg
        destinations = []

        def decrypt(*args, **kwargs):
            destinations.append(args[1])
            return original(*args, **kwargs)

        def fail_restore(container, arguments, **kwargs):
            if arguments[0] == "psql":
                return b"empty\n"
            raise backup.BackupError("Restore failed")

        with patch.object(backup, "_gpg", side_effect=decrypt), patch.object(backup, "_docker", side_effect=fail_restore):
            with self.assertRaises(backup.BackupError):
                self.do_restore()
        self.assertTrue(destinations)
        self.assertTrue(all(not Path(destination).exists() for destination in destinations))

    def test_secret_is_passed_by_fd_and_not_argument_or_environment(self):
        original = backup.subprocess.run
        calls = []

        def observe(command, **kwargs):
            calls.append((command, kwargs))
            return original(command, **kwargs)

        with patch.object(backup.subprocess, "run", side_effect=observe):
            self.make_archive()
        self.assertEqual(len(calls), 1)
        command, kwargs = calls[0]
        self.assertEqual(command[0], "gpg")
        self.assertIn("--passphrase-fd", command)
        self.assertNotIn("--passphrase", command)
        self.assertTrue(kwargs["pass_fds"])
        secret = self.key.read_text().strip()
        self.assertTrue(all(secret not in str(argument) for argument in command))
        self.assertNotIn("env", kwargs)

    def test_invalid_identifiers_fail_before_any_external_tool(self):
        for override in ({"container": "--remote"}, {"user": "postgres; DROP DATABASE other"}, {"database": "unsafe/db"}):
            with self.subTest(override=override), patch.object(backup, "_docker") as database:
                with self.assertRaises(backup.BackupError):
                    self.do_backup(**override)
                database.assert_not_called()

    def test_docker_errors_do_not_expose_tool_stderr(self):
        completed = Mock(returncode=1, stderr=b"private credential or customer data", stdout=b"")
        with patch.object(backup.subprocess, "run", return_value=completed):
            with self.assertRaises(backup.BackupError) as failure:
                backup._docker("local-drill", ["pg_dump"])
        self.assertNotIn("private", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
