"""Create deployment credentials once; never replace an existing .env."""

import os
from pathlib import Path
import secrets
import string


def strong_password():
    alphabet = string.ascii_letters + string.digits + "!@%_-+"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(32))
        if all(
            any(char in group for char in value)
            for group in (
                string.ascii_lowercase,
                string.ascii_uppercase,
                string.digits,
                "!@%_-+",
            )
        ):
            return value


root = Path(__file__).resolve().parents[2]
template = (root / ".env.example").read_text()
values = {
    "ARGILLA_PASSWORD": strong_password(),
    "ARGILLA_API_KEY": secrets.token_urlsafe(32),
    "POSTGRES_PASSWORD": secrets.token_hex(24),
}
for key, value in values.items():
    template = template.replace(f"{key}=\n", f"{key}={value}\n")
path = root / ".env"
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit("Existing .env preserved; no credentials changed")
with os.fdopen(fd, "w") as output:
    output.write(template)
print(f"Created {path} with mode 0600; credentials are not printed")
