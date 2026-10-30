import os
import time

from openai import OpenAI

import llm
from db import run_query
from main import clean_sql
from prompts import build_system_prompt
from sql_guard import GuardError, check

MODELS = [
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3.5-bolt-e4b",
    "meta/llama-3.2-11b-vision-instruct",
]
QUESTIONS = [
    "Quel est le chiffre d'affaires par mois en 2017 ?",
    "Top 5 des catégories par chiffre d'affaires",
    "Combien de tickets ouverts ?",
]

client = OpenAI(base_url="https://integrate.api.nvidia.com/v1",
                api_key=os.environ["NVIDIA_API_KEY"], timeout=90)

for m in MODELS:
    print(f"\n=== {m}")
    for q in QUESTIONS:
        t = time.time()
        try:
            r = client.chat.completions.create(
                model=m, temperature=0, max_tokens=1500,
                messages=[{"role": "system", "content": build_system_prompt("directeur")},
                          {"role": "user", "content": q}])
            msg = r.choices[0].message
            raw = msg.content or ""
            if not raw:
                print(f"  VIDE  ({q[:30]}) finish={r.choices[0].finish_reason}")
                continue
            sql = clean_sql(raw)
            cols, rows = run_query(check(sql, "directeur"), "directeur", "")
            print(f"  OK    {round(time.time()-t,1)}s {len(rows)} lignes | {q[:40]}")
        except GuardError as e:
            print(f"  GUARD {q[:30]} -> {e} | {raw[:120]!r}")
        except Exception as e:
            print(f"  ERR   {q[:30]} -> {str(e)[:100]}")