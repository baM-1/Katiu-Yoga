"""Da acceso al Panel de Admin. Si el usuario no existe, lo crea (pide la contraseña).

Uso en el servidor (una vez, para Lalo):
    fly ssh console --pty --app katiu-yoga -u katiu \
      -C "sh -c 'cd /app && python scripts/make_admin.py --email lalo@ejemplo.com --nombre Lalo'"

Después, el resto de usuarios se gestiona desde la propia app: Más → Panel de Admin.
"""

import argparse
import getpass

from sqlmodel import Session

from katiu.accounts.repository import UserRepository
from katiu.accounts.service import AccountError, create_user, make_admin
from katiu.core.db import engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre", default="Admin")
    args = parser.parse_args()

    with Session(engine) as db:
        try:
            if UserRepository(db).by_email(args.email) is None:
                password = getpass.getpass("Contraseña para la app (mín. 8): ")
                if password != getpass.getpass("Repítela: "):
                    raise SystemExit("✗ No coinciden. No se ha cambiado nada.")
                create_user(db, args.email, args.nombre, password)
                print(f"✓ Usuario {args.email} creado")
            make_admin(db, args.email)
        except AccountError as exc:
            raise SystemExit(f"✗ {exc}") from exc
    print(f"✓ {args.email} ya puede entrar en /admin")


if __name__ == "__main__":
    main()
