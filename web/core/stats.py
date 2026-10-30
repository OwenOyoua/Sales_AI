from django.db import connection
from django.db.models import Avg, Count, Q

from .models import QueryLog, Ticket


def fmt(x, d=0):
    """1234567.8 -> '1 234 568' (espace fine, virgule décimale)."""
    return f"{x:,.{d}f}".replace(",", "\u202f").replace(".", ",")


def _query(sql, params=()):
    with connection.cursor() as cur:
        cur.execute(sql, list(params))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _year_sql(year):
    if not year:
        return "", []
    return (" AND o.purchased_at >= %s AND o.purchased_at < %s",
            [f"{year}-01-01", f"{year + 1}-01-01"])


# ---------- Ventes (admin, directeur, vendeur) ----------

def sales_data(year, seller_id=None):
    where = "o.status NOT IN ('canceled','unavailable')"
    params = []
    if seller_id:
        where += " AND i.seller_id = %s"
        params.append(seller_id)
    ys, yp = _year_sql(year)
    where += ys
    params += yp
    frm = "FROM order_items i JOIN orders o ON o.order_id = i.order_id"

    k = _query(f"SELECT coalesce(sum(i.price),0) AS revenue, "
               f"count(DISTINCT i.order_id) AS orders {frm} WHERE {where}", params)[0]
    revenue, orders = float(k["revenue"]), k["orders"]

    monthly = _query(
        f"SELECT to_char(date_trunc('month', o.purchased_at), 'YYYY-MM') AS m, "
        f"sum(i.price) AS v {frm} WHERE {where} GROUP BY 1 ORDER BY 1", params)
    cats = _query(
        f"SELECT coalesce(nullif(p.category_en,''),'(sans catégorie)') AS c, sum(i.price) AS v "
        f"{frm} JOIN products p ON p.product_id = i.product_id "
        f"WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 8", params)

    rw, rp = "1=1", []
    if seller_id:
        rw += (" AND EXISTS (SELECT 1 FROM order_items i "
               "WHERE i.order_id = o.order_id AND i.seller_id = %s)")
        rp.append(seller_id)
    rev = _query(
        f"SELECT round(avg(r.score)::numeric, 2) AS avg_score, count(*) AS n "
        f"FROM order_reviews r JOIN orders o ON o.order_id = r.order_id "
        f"WHERE {rw}{ys}", rp + yp)[0]

    return {
        "kind": "sales",
        "kpis": [
            {"label": "Chiffre d'affaires", "value": "R$ " + fmt(revenue, 2)},
            {"label": "Commandes", "value": fmt(orders)},
            {"label": "Panier moyen", "value": "R$ " + fmt(revenue / orders if orders else 0, 2)},
            {"label": "Note moyenne",
             "value": f"{float(rev['avg_score']):.2f} / 5".replace(".", ",") if rev["avg_score"] else "—"},
        ],
        "charts": {
            "monthly": {"labels": [r["m"] for r in monthly], "values": [float(r["v"]) for r in monthly]},
            "categories": {"labels": [r["c"] for r in cats], "values": [float(r["v"]) for r in cats]},
        },
    }


# ---------- Service après-vente ----------

def sav_data(year):
    ys, yp = _year_sql(year)
    by_status = {r["status"]: r["n"] for r in
                 Ticket.objects.order_by().values("status").annotate(n=Count("id"))}
    statuses = Ticket.Status.choices

    late = _query("SELECT count(*) AS n FROM orders o "
                  f"WHERE o.status = 'delivered' AND o.delivered_at > o.estimated_delivery_at{ys}", yp)[0]["n"]
    low = _query("SELECT count(*) AS n FROM order_reviews r JOIN orders o ON o.order_id = r.order_id "
                 f"WHERE r.score <= 2{ys}", yp)[0]["n"]
    scores = _query("SELECT r.score AS s, count(*) AS n FROM order_reviews r "
                    "JOIN orders o ON o.order_id = r.order_id "
                    f"WHERE 1=1{ys} GROUP BY 1 ORDER BY 1", yp)

    return {
        "kind": "sav",
        "kpis": [
            {"label": "Tickets ouverts", "value": fmt(by_status.get("open", 0))},
            {"label": "Tickets en cours", "value": fmt(by_status.get("in_progress", 0))},
            {"label": "Avis ≤ 2 / 5", "value": fmt(low)},
            {"label": "Livraisons en retard", "value": fmt(late)},
        ],
        "charts": {
            "tickets": {"labels": [label for _, label in statuses],
                        "values": [by_status.get(v, 0) for v, _ in statuses]},
            "scores": {"labels": [f"{r['s']} ★" for r in scores], "values": [r["n"] for r in scores]},
        },
    }


# ---------- Usage de l'IA (admin, directeur) ----------

def ai_usage():
    a = QueryLog.objects.aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(status="ok")),
        failed=Count("id", filter=~Q(status="ok")),
        slow=Count("id", filter=Q(duration_ms__gt=10000)),
        voice=Count("id", filter=Q(via_voice=True)),
        up=Count("id", filter=Q(feedback=1)),
        down=Count("id", filter=Q(feedback=-1)),
        avg_ms=Avg("duration_ms"),
    )
    total, rated = a["total"], a["up"] + a["down"]

    def pct(n, d):
        return f"{round(100 * n / d)} %" if d else "—"

    return {
        "kpis": [
            {"label": "Questions posées", "value": fmt(total)},
            {"label": "Réussies", "value": pct(a["ok"], total)},
            {"label": "👍 sur les questions notées", "value": f"{pct(a['up'], rated)} ({rated} avis)"},
            {"label": "Échecs ou refus", "value": fmt(a["failed"])},
            {"label": "Plus de 10 s", "value": fmt(a["slow"])},
            {"label": "Durée moyenne", "value": f"{(a['avg_ms'] or 0) / 1000:.1f} s".replace(".", ",")},
            {"label": "Dictées à la voix", "value": pct(a["voice"], total)},
        ],
        "to_review": QueryLog.objects.filter(Q(feedback=-1) | ~Q(status="ok"))
                                     .select_related("user")[:10],
    }