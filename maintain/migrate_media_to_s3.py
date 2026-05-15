#!/usr/bin/env python3
"""
Одноразовый скрипт: перенос медиафайлов из локального тома в Minio S3.

NOTE: Этот скрипт находится в maintain/ т.к. директория scripts/ создана Docker с правами root.
Для запуска внутри контейнера скопируйте скрипт или используйте путь ниже.

Использование (из директории services/backend):
  uv run maintain/migrate_media_to_s3.py

Или внутри контейнера:
  docker exec -it eqsitecms-app bash -c "cd /eqsitecms && uv run scripts/migrate_media_to_s3.py"

Переменные окружения (из .env или явно):
  S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME
  POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_NAME
  MEDIA_SOURCE_DIR  # опционально: явно указать директорию с файлами
"""
import asyncio
import json
import os
from pathlib import Path

import aioboto3
import asyncpg


async def main() -> None:
    # --- S3 Config ---
    endpoint = os.environ["S3_ENDPOINT_URL"]
    access_key = os.environ["S3_ACCESS_KEY"]
    secret_key = os.environ["S3_SECRET_KEY"]
    bucket = os.environ.get("S3_BUCKET_NAME", "gallery")

    # --- Locate source dir ---
    source_dirs = []
    if explicit := os.environ.get("MEDIA_SOURCE_DIR"):
        source_dirs = [Path(explicit)]
    else:
        base = Path(__file__).resolve().parents[1]  # services/backend/
        candidates = [
            base / "storage" / "media",
            base / "src" / "media",
        ]
        source_dirs = [p for p in candidates if p.exists() and any(p.iterdir())]

    if not source_dirs:
        print("No media source directories found. Exiting.")
        return

    # --- S3: create bucket + set public read policy ---
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    ) as s3:
        # Create bucket if not exists
        try:
            await s3.head_bucket(Bucket=bucket)
            print(f"Bucket '{bucket}' already exists.")
        except Exception:
            await s3.create_bucket(Bucket=bucket)
            print(f"Bucket '{bucket}' created.")

        # Set public read policy
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
        await s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy),
        )
        print("Bucket policy set to public read.")

        # --- Upload files ---
        total = 0
        errors = []
        for source_dir in source_dirs:
            print(f"Scanning: {source_dir}")
            for file_path in source_dir.iterdir():
                if not file_path.is_file():
                    continue
                filename = file_path.name
                try:
                    content = file_path.read_bytes()
                    await s3.put_object(Bucket=bucket, Key=filename, Body=content)
                    total += 1
                    print(f"  Uploaded: {filename}")
                except Exception as exc:
                    errors.append((filename, str(exc)))
                    print(f"  ERROR: {filename} — {exc}")

        print(f"\nUploaded: {total} files, Errors: {len(errors)}")
        if errors:
            print("Failed files:")
            for name, err in errors:
                print(f"  {name}: {err}")

    # --- DB: verify path column contains only filenames ---
    # path column stores only filename (no directory prefix).
    # If any row has a path with '/' or '\\', strip to basename.
    db_url = (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_NAME']}"
    )
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            "SELECT id, path FROM photos WHERE path LIKE '%/%' OR path LIKE '%\\\\%'"
        )
        if rows:
            print(f"\nFound {len(rows)} DB rows with directory-prefixed paths. Fixing...")
            for row in rows:
                filename_only = Path(row["path"]).name
                await conn.execute(
                    "UPDATE photos SET path = $1 WHERE id = $2",
                    filename_only,
                    row["id"],
                )
                print(f"  Fixed: {row['path']} -> {filename_only}")
        else:
            print("\nDB paths are clean (filename-only). No updates needed.")
    finally:
        await conn.close()

    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
