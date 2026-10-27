"""Initialize a new deployment without resetting existing users or printing secrets."""

import asyncio
import os
import subprocess
import sys

from sqlalchemy import select

from argilla_server.contexts import accounts
from argilla_server.database import AsyncSessionLocal
from argilla_server.models import User, UserRole, Workspace


async def initialize_owner():
    async with AsyncSessionLocal() as session:
        # Existing deployments retain their accounts, credentials and workspaces.
        if await session.scalar(select(User.id).limit(1)) is not None:
            print("Existing users found; preserving accounts", flush=True)
            return
        username = os.environ["USERNAME"]
        workspace = Workspace(name=os.environ.get("WORKSPACE", "admin"))
        await User.create(
            session,
            username=username,
            first_name=username,
            role=UserRole.owner,
            password_hash=accounts.hash_password(os.environ["PASSWORD"]),
            api_key=os.environ["API_KEY"],
            workspaces=[workspace],
        )
        print("Initial owner and workspace created", flush=True)


if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "argilla_server", "database", "migrate"], check=True
    )
    asyncio.run(initialize_owner())
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "argilla_server:app",
            "--host",
            "0.0.0.0",
            "--port",
            "6900",
        ],
    )
