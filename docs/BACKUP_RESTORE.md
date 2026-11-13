# Encrypted database backups and local recovery — M5-07

`scripts/database_backup.py` creates encrypted PostgreSQL custom-format backups and restores a trusted archive into an explicitly confirmed, empty, isolated database. `scripts/backup_restore_drill.py` exercises the workflow with synthetic data in its own disposable PostgreSQL 16 container. No hosted service or new Python package is required.

## Operator requirements

- Use the managed local Docker socket at `/var/run/docker.sock`, PostgreSQL client tools inside the selected database container, Python 3.12 and GnuPG 2.4. The helper deliberately ignores inherited remote Docker endpoint/context/TLS selectors. It does not pull images, configure credentials, create databases or change server authentication.
- Existing PostgreSQL authentication must work noninteractively inside the selected container. Client commands use `--no-password`; configure the database's approved local authentication rather than entering passwords through this script or command arguments.
- Provision a strong, unique passphrase through secure secret storage as a regular file owned by the current operator, mode `0600` or `0400`, containing one nonempty line. Symlinks, group/world access, empty keys, multiline keys and NUL bytes are rejected. Never put the value in chat, source, shell arguments, environment variables or logs. Keep a separately protected recoverable copy: a lost key makes the encrypted backup unusable.
- Create the output directory beforehand with private access. Backups contain the entire database, including personal and financial records. Store archives outside the checkout with appropriate filesystem, retention, offsite encryption and operator access controls.

```sh
python scripts/database_backup.py backup \
  --container <local-database-container> --user <database-role> --database <source-database> \
  --output <private-backup-directory>/reseller-unique-timestamp.gpg \
  --passphrase-file <secure-passphrase-file>
```

The helper runs `pg_dump --format=custom --no-owner --no-acl`, encrypts using GnuPG AES-256 and its integrity-protected format, then atomically publishes a mode-`0600` archive. Existing paths are never overwritten, including a competing writer creating the destination during backup. Dump/encryption failures leave no published incomplete archive. Temporary plaintext and the temporary GnuPG home live in private directories and are removed on ordinary success/failure. Account for operating-system crashes, disk snapshots and storage encryption separately; deleting a temporary file is not guaranteed physical media erasure.

## Restore only into an offline empty database

Create a **new isolated database** using a trusted operator procedure and keep application workers and all other writers disconnected. Match PostgreSQL client/server versions appropriately; a backup cannot be assumed restorable into an older incompatible major version. Use only an archive from your trusted backup process: PostgreSQL archives contain executable schema definitions, and encryption does not make an untrusted source safe.

```sh
python scripts/database_backup.py restore \
  --container <local-database-container> --user <database-role> --database <new-empty-database> \
  --archive <private-backup-directory>/reseller-unique-timestamp.gpg \
  --passphrase-file <secure-passphrase-file> \
  --confirm-empty-target <new-empty-database>
```

The confirmation must exactly match the explicit target name. GnuPG must finish decryption and integrity verification successfully before the helper contacts PostgreSQL. The plaintext must have the PostgreSQL custom archive header. The target must contain no user relations, functions, types or additional user schemas. The helper then invokes `pg_restore --exit-on-error --single-transaction --no-owner --no-acl`, with no `--clean`, drop or overwrite mode. The original source database is never a restore target unless an operator explicitly supplies it, and a nonempty target is refused.

The empty check and restore are separate connections. **They cannot exclude a concurrent external writer**; the target must be isolated/offline throughout. A conflicting restore error rolls back its transaction, but that is not a substitute for target isolation or trusting the archive. After restoration, verify ownership, payment/order state, unique constraints, audit records and migrations before reconnecting an application. Do not enable sales/fulfillment solely because restore succeeded. Restoring an old snapshot can replay uncertain financial state; reconcile gateway and registrar evidence before restarting workers.

## Repeatable local drill

Ensure `postgres:16-alpine` is already present, then run:

```sh
python -m unittest scripts.test_database_backup -v
python scripts/backup_restore_drill.py
```

The drill uses a unique container with its own ownership label, no host port and no network, bounded CPU/memory and synthetic customer/domain/order/payment/audit fixtures. Local trust authentication is used only inside that disposable, disconnected container; it is not a production recommendation. The script does not pull images and cleans only the container/anonymous volume bearing its own run label and its own private temporary files. It preserves existing development containers and databases.

Checks include restored row/ownership/payment/audit equality, identity sequence continuation, foreign-key/unique/positive-amount constraints, refused overwrite of an existing archive, wrong-passphrase and corrupt-ciphertext rejection without target mutation, and refusal to restore over a sentinel table. Unit guards use real GnuPG and a simulated Docker boundary; the separate drill uses real PostgreSQL tools and checks the actual restore. CI may run both commands after installing GnuPG and preparing the PostgreSQL 16 image; do not describe the guard tests alone as a real database restore.

Local evidence: all **17 guard tests passed with zero skips**, compilation/diff checks passed, and the real PostgreSQL 16 drill passed every check above. The drill's labeled container, anonymous volume and private temporary keys/archive/plaintext were removed. A real restore exposed and fixed a buffered file-descriptor offset issue; the unit roundtrip now reads the descriptor directly, matching how `pg_restore` receives its input.

## Reuse, limits and acceptance

**CONFIGURE / REUSE:** PostgreSQL's maintained `pg_dump`/`pg_restore` tools ([official backup documentation](https://www.postgresql.org/docs/16/backup-dump.html), PostgreSQL License), [GnuPG](https://www.gnupg.org/documentation/) encryption/integrity and passphrase-FD interface (GPL-3.0-or-later tooling), and Python's standard subprocess/tempfile libraries. No GnuPG implementation is copied or linked into the application and no new runtime dependency or project-license decision is introduced. **BUILD:** bounded operator orchestration, preconditions and synthetic verification.

This local tooling does **not** configure scheduled backups, encrypted offsite replication, key escrow/rotation, immutable retention, failure alerts, hosted-database snapshots or an on-call process. The synthetic restore is not AT19's clean staging restoration of actual application data, and does not verify every application workflow after restore. The owner must define RPO/RTO, retention/legal policy, storage and identity controls; run an approved full staging recovery and external-transaction reconciliation before accepting M5-07/AT19 or enabling production. Keep those checklist gates open until that evidence exists.

Local evidence: all **17 guard tests passed with zero skips** using real GnuPG. The separate real PostgreSQL 16 drill passed every restore/ownership/sequence/constraint and refusal check, then verified removal of its owned container and temporary keys. Compilation and diff checks passed. CI now runs the guard suite and real isolated drill in its own backup-recovery job.
