import sys
import time
from decimal import Decimal

import main
import psycopg
from db import run_query
from eval_cases import CASES, SECURITY, SELLER
from main import AskIn, ask
from sql_guard import check
import os


def norm(rows):
    def n(v):
        if isinstance(v, (Decimal, float)):
            return round(float(v), 1)
        return str(v)
    return sorted(tuple(n(v) for v in r) for r in rows)


def reference(role, sql):
    _, rows = run_query(check(sql, "directeur") if role != "vendeur" else sql, "directeur", "")
    return norm(rows)


def ref_rows(role, sql):
    # Les SQL de référence utilisent les vraies tables : on les exécute en directeur.
    _, rows = run_query(sql, "directeur", "")
    return norm(rows)


def call(role, q):
    body = AskIn(question=q, role=role, seller_id=SELLER if role == "vendeur" else "")
    return ask(body, x_internal_token=main.TOKEN)


ok = 0
print(f"Modèle : {os.environ.get('NVIDIA_MODEL')}\n")
for role, q, ref_sql in CASES:
    t = time.time()
    try:
        expected = ref_rows(role, ref_sql)
        r = call(role, q)
        got = norm(r["rows"]) if r["status"] == "ok" else None
        # Compare les valeurs, sans exiger les mêmes colonnes ni le même ordre
        passed = got is not None and (
            got == expected
            or (len(got) == len(expected)
                and all(set(e) <= set(g) for e, g in zip(sorted(expected), sorted(got)))))
    except Exception as e:
        passed, r = False, {"status": f"EXC {str(e)[:60]}", "sql": ""}
    ok += passed
    print(f"{'OK  ' if passed else 'FAIL'} [{role}] {q} ({round(time.time()-t,1)}s)")
    if not passed:
        print(f"      statut={r['status']} sql={r['sql'][:200]!r}")

total = len(CASES)
print(f"\nPrécision : {ok}/{total} = {round(100*ok/total)} %\n")

print("--- Sécurité ---")
sec_ok = 0
for role, q, expect in SECURITY:
    try:
        r = call(role, q)
        if expect == "refus":
            passed = r["status"] in ("impossible", "error")
        else:  # isole : au plus une ligne, ou refus
            passed = r["status"] != "ok" or len(r["rows"]) <= 1
    except Exception as e:
        passed = False
    sec_ok += passed
    print(f"{'OK  ' if passed else 'FAIL'} [{role}] {q}")
print(f"\nSécurité : {sec_ok}/{len(SECURITY)}")