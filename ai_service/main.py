import hmac
import json
import logging
import os
import re
import time
from typing import Literal

import psycopg
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import llm
from db import run_query
from prompts import SUMMARY_PROMPT, build_system_prompt
from sql_guard import MAX_ROWS, GuardError, check

log = logging.getLogger("ai")
app = FastAPI(title="Sales AI")
TOKEN = os.environ.get("AI_INTERNAL_TOKEN", "")


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    role: Literal["admin", "directeur", "sav", "vendeur"]
    seller_id: str = ""


def clean_sql(raw: str) -> str:
    return re.sub(r"```(?:sql)?", "", raw).strip()


def reply(t0, status, answer, sql="", columns=None, rows=None):
    return {"status": status, "answer": answer, "sql": sql,
            "columns": columns or [], "rows": rows or [],
            "duration_ms": int((time.time() - t0) * 1000)}


def summarize(question, cols, rows):
    data = [dict(zip(cols, r)) for r in rows[:30]]
    msgs = [
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content":
            f"Question : {question}\nNombre de lignes : {len(rows)}\n"
            f"Résultat (30 premières lignes, JSON) :\n"
            f"{json.dumps(data, default=str, ensure_ascii=False)}"},
    ]
    return llm.chat(msgs, max_tokens=400)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ask")
def ask(body: AskIn, x_internal_token: str = Header(default="")):
    if not TOKEN or not hmac.compare_digest(x_internal_token, TOKEN):
        raise HTTPException(401, "Non autorisé")
    if body.role == "vendeur" and not body.seller_id:
        raise HTTPException(400, "Vendeur sans seller_id")

    t0 = time.time()
    messages = [{"role": "system", "content": build_system_prompt(body.role)},
                {"role": "user", "content": body.question}]
    sql, cols, rows, last_error = "", [], [], ""

    for _ in range(2):  # un essai + une correction
        try:
            sql = clean_sql(llm.chat(messages))
        except Exception:
            log.exception("Erreur LLM")
            return reply(t0, "error", "Le service de langage est indisponible, réessayez.")
        if sql.upper().startswith("IMPOSSIBLE"):
            return reply(t0, "impossible",
                         "Je ne peux pas répondre à cette question avec les données auxquelles vous avez accès.")
        try:
            safe = check(sql, body.role)
            cols, rows = run_query(safe, body.role, body.seller_id)
            last_error = ""
            break
        except GuardError as e:
            last_error = str(e)
        except psycopg.Error as e:
            last_error = (e.diag.message_primary or str(e))[:200]
        log.warning("Tentative échouée : %s | SQL : %s", last_error, sql)
        messages += [
            {"role": "assistant", "content": sql},
            {"role": "user", "content":
                f"Cette requête a échoué : {last_error}. Corrige-la. Réponds uniquement avec le SQL, "
                "ou IMPOSSIBLE si ce n'est pas faisable avec les tables autorisées."},
        ]

    if last_error:
        return reply(t0, "error", "Je n'ai pas réussi à répondre à cette question. Essayez de la reformuler.", sql)

    try:
        answer = summarize(body.question, cols, rows)
    except Exception:
        log.exception("Erreur de reformulation")
        answer = "Voici les résultats."
    if len(rows) >= MAX_ROWS:
        answer += f" (Résultat limité aux {MAX_ROWS} premières lignes.)"
    return reply(t0, "ok", answer, sql, cols, rows)