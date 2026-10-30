import os

import psycopg

ROLE_MAP = {"admin": "ai_directeur", "directeur": "ai_directeur",
            "sav": "ai_sav", "vendeur": "ai_vendeur"}


def run_query(sql: str, role: str, seller_id: str):
    """Exécute sous le rôle SQL du profil, dans une transaction annulée à la fin."""
    with psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        dbname=os.environ["POSTGRES_DB"],
        user="ai_login",
        password=os.environ["AI_DB_PASSWORD"],
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL ROLE {ROLE_MAP[role]}")  # valeur issue d'un dict fixe
            cur.execute("SELECT set_config('app.seller_id', %s, true)", (seller_id or "",))
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
        conn.rollback()
    return cols, rows