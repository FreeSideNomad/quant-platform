"""`audit-verify` — walk the audit_log chain and report integrity."""

from __future__ import annotations

import asyncio
import sys

import typer

from app.audit.log import verify_audit_chain
from app.infra.db import session_scope

app = typer.Typer(help="Verify the audit_log hash chain from genesis to the latest row.")


async def _verify() -> int:
    async with session_scope() as session:
        result = await verify_audit_chain(session)
    typer.echo(
        f"AuditChainCheck(ok={result.ok}, checked={result.checked}, "
        f"first_break={result.first_break}, detail={result.detail!r})"
    )
    return 0 if result.ok else 1


@app.callback(invoke_without_command=True)
def main() -> None:
    exit_code = asyncio.run(_verify())
    sys.exit(exit_code)


if __name__ == "__main__":
    app()
