#!/usr/bin/env python3
"""Encrypted PostgreSQL backups via the managed local Docker socket and GnuPG.

No secret values appear in command arguments, environment variables or output.
Restore accepts a trusted backup into an explicitly confirmed, empty target only.
"""
import argparse
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile


class BackupError(Exception):
    """A sanitized operator error; never include tool stderr or secret values."""


EMPTY_QUERY = """SELECT CASE WHEN
 EXISTS (SELECT 1 FROM pg_namespace WHERE nspname <> 'public'
         AND nspname <> 'information_schema' AND nspname !~ '^pg_')
 OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_')
 OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_')
 OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_')
 THEN 'nonempty' ELSE 'empty' END;"""


def _targets(container, user, database):
    if not isinstance(container, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container):
        raise BackupError("Invalid local container name")
    for value in (user, database):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", value):
            raise BackupError("Use an explicit simple database and role name")


def _docker(container, arguments, *, input_file=None, output_file=None, capture=False):
    environment = os.environ.copy()
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        environment.pop(name, None)
    try:
        result = subprocess.run(
            ["docker", "--host=unix:///var/run/docker.sock", "exec", "-i", container, *arguments],
            stdin=input_file, stdout=subprocess.PIPE if capture else (output_file or subprocess.DEVNULL),
            stderr=subprocess.PIPE, env=environment, check=False,
        )
    except OSError:
        raise BackupError("Local Docker/PostgreSQL operation could not start") from None
    if result.returncode:
        tool = arguments[0] if arguments and arguments[0] in ("pg_dump", "pg_restore", "psql") else "client"
        raise BackupError(f"Local Docker/PostgreSQL {tool} operation failed; verify the target and client/server versions")
    return result.stdout if capture else None


def _passphrase_fd(path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or not 1 <= info.st_size <= 4096):
            raise BackupError("Passphrase file must be private, owned, regular and nonempty")
        value = os.read(descriptor, 4097)
        line = value[:-1] if value.endswith(b"\n") else value
        if not line.strip() or b"\n" in line or b"\r" in line or b"\0" in line:
            raise BackupError("Passphrase file must contain one nonempty line")
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        raise BackupError("Cannot securely open the passphrase file") from None
    except BackupError:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _gpg(source, destination, passphrase_file, home, *, decrypt=False):
    key_fd = _passphrase_fd(passphrase_file)
    try:
        command = ["gpg", "--no-options", "--homedir", str(home), "--batch", "--quiet", "--yes",
                   "--pinentry-mode", "loopback", "--no-symkey-cache", "--passphrase-fd", str(key_fd),
                   "--output", str(destination)]
        command += (["--decrypt", str(source)] if decrypt else
                    ["--symmetric", "--cipher-algo", "AES256", "--force-mdc", "--compress-algo", "none", str(source)])
        try:
            result = subprocess.run(command, pass_fds=(key_fd,), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, check=False)
        except OSError:
            raise BackupError("GnuPG could not start") from None
        if result.returncode:
            raise BackupError("Backup decryption/integrity verification failed" if decrypt else "Backup encryption failed")
        os.chmod(destination, 0o600)
    finally:
        os.close(key_fd)


def backup_database(container, user, database, output, passphrase_file):
    _targets(container, user, database)
    output = Path(output)
    if os.path.lexists(output):
        raise BackupError("Backup destination already exists; nothing was overwritten")
    # Validate the key before contacting the database, without disclosing it.
    key_fd = _passphrase_fd(passphrase_file)
    os.close(key_fd)
    try:
        with tempfile.TemporaryDirectory(prefix=".pg-backup-", dir=output.parent) as directory:
            private = Path(directory)
            plain, encrypted, home = private / "database.dump", private / "database.gpg", private / "gnupg"
            home.mkdir(mode=0o700)
            with plain.open("xb") as dump:
                os.chmod(plain, 0o600)
                _docker(container, ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--no-password",
                                    "--username", user, "--dbname", database], output_file=dump)
            _gpg(plain, encrypted, passphrase_file, home)
            with encrypted.open("rb") as archive:
                os.fsync(archive.fileno())
            # Same-filesystem exclusive link makes publication atomic and race-safe.
            os.link(encrypted, output, follow_symlinks=False)
            directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except FileExistsError:
        raise BackupError("Backup destination already exists; nothing was overwritten") from None
    except OSError:
        raise BackupError("Cannot write the private backup destination") from None
    return output


def restore_database(container, user, database, archive, passphrase_file, confirm_empty_target):
    _targets(container, user, database)
    if confirm_empty_target != database:
        raise BackupError("Restore requires --confirm-empty-target matching the target database")
    archive = Path(archive)
    if not archive.is_file():
        raise BackupError("Encrypted backup is not a regular file")
    try:
        with tempfile.TemporaryDirectory(prefix="pg-restore-") as directory:
            private = Path(directory)
            plain, home = private / "verified.dump", private / "gnupg"
            home.mkdir(mode=0o700)
            # Never stream tentative GPG output into PostgreSQL: exit zero first.
            _gpg(archive, plain, passphrase_file, home, decrypt=True)
            # The child reads the OS descriptor directly; avoid a buffered seek
            # that can leave that descriptor ahead of Python's logical offset.
            with plain.open("rb", buffering=0) as dump:
                if dump.read(5) != b"PGDMP":
                    raise BackupError("Decrypted file is not a PostgreSQL custom-format archive")
                dump.seek(0)
                state = _docker(container, ["psql", "--no-psqlrc", "--no-password", "--set", "ON_ERROR_STOP=1", "--tuples-only",
                                            "--no-align", "--username", user, "--dbname", database,
                                            "--command", EMPTY_QUERY], capture=True)
                if state.strip() != b"empty":
                    raise BackupError("Restore target is not empty; nothing was restored")
                _docker(container, ["pg_restore", "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl", "--no-password",
                                    "--username", user, "--dbname", database], input_file=dump)
    except OSError:
        raise BackupError("Cannot read the encrypted backup or private restore workspace") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("backup", "restore"):
        command = subcommands.add_parser(name)
        for option in ("container", "user", "database", "passphrase-file"):
            command.add_argument("--" + option, required=True)
        command.add_argument("--output" if name == "backup" else "--archive", required=True)
        if name == "restore":
            command.add_argument("--confirm-empty-target", required=True)
    args = vars(parser.parse_args(argv))
    operation = args.pop("command")
    try:
        if operation == "backup":
            backup_database(**args)
        else:
            restore_database(**args)
    except BackupError as exc:
        parser.exit(1, str(exc) + "\n")
    print("Encrypted backup created" if operation == "backup" else "Backup restored into the confirmed empty target")


if __name__ == "__main__":
    main()
