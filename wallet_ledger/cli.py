"""Operator commands: wallet-ledger {migrate,create-key,openapi}."""

import argparse
import os
import sys

import yaml

from wallet_ledger.store.db import DEFAULT_DATABASE_URL, make_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wallet-ledger")
    parser.add_argument("--db", default=os.environ.get("WALLET_DB_URL", DEFAULT_DATABASE_URL))
    sub = parser.add_subparsers(dest="command", required=True)
    migrate_cmd = sub.add_parser("migrate", help="apply or roll back migrations")
    migrate_cmd.add_argument("--to", type=int, help="target version (default: latest)")
    key_cmd = sub.add_parser("create-key", help="create an API key and print it once")
    key_cmd.add_argument("name")
    sub.add_parser("openapi", help="print the OpenAPI spec as YAML")
    args = parser.parse_args(argv)

    if args.command == "openapi":
        from wallet_ledger.app import create_app

        spec = create_app(args.db).openapi()
        sys.stdout.write(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        return 0

    from wallet_ledger.service.auth import AuthService
    from wallet_ledger.store.migrate import migrate

    engine = make_engine(args.db)
    if args.command == "migrate":
        print(f"schema at version {migrate(engine, args.to)}")
    else:
        migrate(engine)
        print(AuthService(engine).create_api_key(args.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
