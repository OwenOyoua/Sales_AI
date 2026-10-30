import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

MAX_ROWS = 200


class GuardError(Exception):
    pass


_SETOP = getattr(exp, "SetOperation", exp.Union)

_DIR = {"customers", "sellers", "products", "orders", "order_items",
        "order_payments", "order_reviews", "tickets"}
ALLOWED_TABLES = {
    "admin": _DIR,
    "directeur": _DIR,
    "sav": {"customers", "products", "orders", "order_items",
            "order_reviews", "tickets"},
    "vendeur": {"v_orders", "v_order_items", "v_products", "v_reviews"},
}

# Fonctions "inconnues" de sqlglot qu'on accepte. Tout le reste est refusé
# (set_config, pg_sleep, pg_read_file, dblink...).
ALLOWED_ANON = {"date_part", "age", "to_char", "to_date", "trunc", "ceil",
                "floor", "abs", "length", "lower", "upper", "initcap",
                "concat", "split_part", "left", "right"}

FORBIDDEN = tuple(
    getattr(exp, n) for n in (
        "Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable",
        "Command", "Set", "Into", "Lock", "Merge", "Copy", "Use",
        "Transaction", "Commit", "Rollback") if hasattr(exp, n))


def check(sql: str, role: str) -> str:
    """Valide le SQL et renvoie une version sûre (reconstruite, avec LIMIT)."""
    allowed = ALLOWED_TABLES.get(role)
    if allowed is None:
        raise GuardError("Rôle inconnu.")
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise GuardError("Requête vide.")
    try:
        stmts = sqlglot.parse(sql, read="postgres")
    except SqlglotError as e:
        raise GuardError(f"SQL illisible : {str(e)[:150]}")
    if len(stmts) != 1 or stmts[0] is None:
        raise GuardError("Une seule requête est autorisée.")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, _SETOP)):
        raise GuardError("Seules les requêtes SELECT sont autorisées.")
    if tree.find(*FORBIDDEN):
        raise GuardError("Instruction interdite.")

    for f in tree.find_all(exp.Anonymous):
        if f.name.lower() not in ALLOWED_ANON:
            raise GuardError(f"Fonction interdite : {f.name}")

    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if t.db or t.catalog:
            raise GuardError("Les schémas ne sont pas autorisés.")
        name = t.name.lower()
        if name in ctes:
            continue
        if name not in allowed:
            raise GuardError(f"Table non autorisée : {name or '?'}")

    safe = tree.sql(dialect="postgres")
    return f"SELECT * FROM ({safe}) AS q LIMIT {MAX_ROWS}"