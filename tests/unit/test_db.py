from sqlalchemy import text

from katiu.core.db import make_engine


def test_pragmas_de_sqlite(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'x.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        # Litestream necesita que la app espere al candado en vez de fallar.
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
