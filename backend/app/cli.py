"""Administrative CLI for role assignment.

Roles are never assignable through the public HTTP API. Until the admin panel
(Sprint 8) exists, operators assign them from the server shell:

    python -m app.cli assign-role --email author@example.com --role course_author
    python -m app.cli remove-role --email author@example.com --role course_author
    python -m app.cli list-roles
    python -m app.cli list-users

The tool talks to the database directly, so holding shell access (and the
database credentials in `.env`) is the actual authorisation boundary. It is not
reachable over the network.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import select

from app.core.database import SessionFactory
from app.modules.users.models import Role, User
from app.modules.users.rbac import RoleCode
from app.modules.users.repository import UserRepository


async def _assign(email: str, role_code: str, *, remove: bool) -> int:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        user = await repository.get_by_email(email)
        if user is None:
            print(f"error: no account with email {email!r}", file=sys.stderr)
            return 1

        if role_code == RoleCode.GUEST:
            print("error: the guest role is not assignable to accounts", file=sys.stderr)
            return 2

        role = await repository.get_role_by_code(role_code)
        if role is None:
            print(
                f"error: unknown role {role_code!r}; apply migrations first",
                file=sys.stderr,
            )
            return 2

        assigned = {item.code for item in user.roles}
        if remove:
            if role_code not in assigned:
                print(f"{email}: role {role_code} is not assigned")
                return 0
            user.roles = [item for item in user.roles if item.code != role_code]
            action = "removed"
        else:
            if role_code in assigned:
                print(f"{email}: role {role_code} is already assigned")
                return 0
            user.roles.append(role)
            action = "assigned"

        await session.commit()
        print(f"{email}: role {role_code} {action}")
        return 0


async def _list_roles() -> int:
    async with SessionFactory() as session:
        roles = list(await session.scalars(select(Role).order_by(Role.code)))
        for role in roles:
            assignable = "no" if role.code == RoleCode.GUEST else "yes"
            print(f"{role.code:<24} assignable={assignable:<3} {role.name}")
    return 0


async def _list_users() -> int:
    async with SessionFactory() as session:
        users = list(await session.scalars(select(User).order_by(User.email)))
        for user in users:
            print(f"{user.email:<40} {', '.join(user.role_codes) or '-'}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Education Platform administrative CLI (roles, diagnostics).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("assign-role", "Attach an existing role to an account."),
        ("remove-role", "Detach a role from an account."),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--email", required=True, help="Account email.")
        sub.add_argument(
            "--role",
            required=True,
            help="Role code, e.g. course_author, teacher or admin.",
        )

    subparsers.add_parser("list-roles", help="List roles and whether they are assignable.")
    subparsers.add_parser("list-users", help="List accounts with their roles.")
    return parser


async def _run(argv: Sequence[str]) -> int:
    args = _build_parser().parse_args(list(argv))

    if args.command == "assign-role":
        return await _assign(args.email, args.role, remove=False)
    if args.command == "remove-role":
        return await _assign(args.email, args.role, remove=True)
    if args.command == "list-roles":
        return await _list_roles()
    if args.command == "list-users":
        return await _list_users()

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    main()
