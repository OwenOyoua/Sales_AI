from sql_guard import GuardError, check

CASES = [
    ("SELECT count(*) FROM orders", "directeur", True),
    ("WITH t AS (SELECT * FROM orders) SELECT count(*) FROM t", "sav", True),
    ("SELECT count(*) FROM v_orders", "vendeur", True),
    ("SELECT * FROM orders; DROP TABLE orders", "directeur", False),
    ("DELETE FROM orders", "directeur", False),
    ("SELECT set_config('app.seller_id','x',true)", "vendeur", False),
    ("SELECT * FROM orders", "vendeur", False),
    ("SELECT * FROM core_user", "directeur", False),
    ("SELECT * FROM pg_catalog.pg_tables", "directeur", False),
    ("SELECT pg_sleep(5)", "directeur", False),
    ("SELECT * FROM order_payments", "sav", False),
]
bad = 0
for sql, role, ok in CASES:
    try:
        check(sql, role)
        passed = ok
    except GuardError:
        passed = not ok
    bad += not passed
    print("OK  " if passed else "FAIL", role, "|", sql)
print("Tout est bon." if not bad else f"{bad} test(s) en échec.")