"""Pone una contraseña nueva a un usuario (por si se olvida).

Las contraseñas se guardan cifradas con argon2: nadie puede "verlas", ni siquiera desde aquí.
Lo que sí se puede es poner una nueva.

Uso en el servidor:
    fly ssh console --pty --app katiu-yoga -u katiu \
      -C "sh -c 'cd /app && python scripts/reset_password.py --email kat@ejemplo.com'"
"""

import argparse
import getpass

from sqlmodel import Session

from katiu.accounts.service import AccountError, reset_password
from katiu.core.db import engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    new = getpass.getpass("Contraseña nueva (mín. 8): ")
    if new != getpass.getpass("Repítela: "):
        raise SystemExit("✗ No coinciden. No se ha cambiado nada.")
    with Session(engine) as db:
        try:
            reset_password(db, args.email, new)
        except AccountError as exc:
            raise SystemExit(f"✗ {exc}") from exc
    print(f"✓ Contraseña cambiada para {args.email}")


if __name__ == "__main__":
    main()
