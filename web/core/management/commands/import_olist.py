import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (Customer, Order, OrderItem, Payment, Product, Review,
                         Seller)

BATCH = 5000


def s(v):
    return (v or "").strip()


def to_int(v):
    v = s(v)
    return int(float(v)) if v else None


def to_dec(v):
    return Decimal(s(v) or "0")


def to_dt(v):
    v = s(v)
    if not v:
        return None
    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


class Command(BaseCommand):
    help = "Charge les CSV Olist dans PostgreSQL (efface les données Olist existantes)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="/data")

    def load(self, model, path, build):
        batch, total = [], 0
        for row in read(path):
            batch.append(build(row))
            if len(batch) >= BATCH:
                model.objects.bulk_create(batch)
                total += len(batch)
                batch = []
        if batch:
            model.objects.bulk_create(batch)
            total += len(batch)
        self.stdout.write(f"  {model.__name__}: {total} lignes")

    @transaction.atomic
    def handle(self, *args, **opts):
        d = Path(opts["dir"])
        if not (d / "olist_orders_dataset.csv").exists():
            raise CommandError(f"CSV introuvables dans {d}")

        self.stdout.write("Nettoyage...")
        for m in (Review, Payment, OrderItem, Order, Product, Seller, Customer):
            m.objects.all().delete()

        self.stdout.write("Chargement...")
        self.load(Customer, d / "olist_customers_dataset.csv", lambda r: Customer(
            customer_id=r["customer_id"], customer_unique_id=r["customer_unique_id"],
            zip_code_prefix=s(r["customer_zip_code_prefix"]),
            city=s(r["customer_city"]), state=s(r["customer_state"])))

        self.load(Seller, d / "olist_sellers_dataset.csv", lambda r: Seller(
            seller_id=r["seller_id"], zip_code_prefix=s(r["seller_zip_code_prefix"]),
            city=s(r["seller_city"]), state=s(r["seller_state"])))

        trad = {r["product_category_name"]: r["product_category_name_english"]
                for r in read(d / "product_category_name_translation.csv")}
        self.load(Product, d / "olist_products_dataset.csv", lambda r: Product(
            product_id=r["product_id"], category=s(r["product_category_name"]),
            category_en=trad.get(s(r["product_category_name"]), s(r["product_category_name"])),
            name_length=to_int(r["product_name_lenght"]),
            description_length=to_int(r["product_description_lenght"]),
            photos_qty=to_int(r["product_photos_qty"]), weight_g=to_int(r["product_weight_g"]),
            length_cm=to_int(r["product_length_cm"]), height_cm=to_int(r["product_height_cm"]),
            width_cm=to_int(r["product_width_cm"])))

        self.load(Order, d / "olist_orders_dataset.csv", lambda r: Order(
            order_id=r["order_id"], customer_id=r["customer_id"], status=r["order_status"],
            purchased_at=to_dt(r["order_purchase_timestamp"]), approved_at=to_dt(r["order_approved_at"]),
            shipped_at=to_dt(r["order_delivered_carrier_date"]),
            delivered_at=to_dt(r["order_delivered_customer_date"]),
            estimated_delivery_at=to_dt(r["order_estimated_delivery_date"])))

        self.load(OrderItem, d / "olist_order_items_dataset.csv", lambda r: OrderItem(
            order_id=r["order_id"], item_number=int(r["order_item_id"]),
            product_id=r["product_id"], seller_id=r["seller_id"],
            shipping_limit_at=to_dt(r["shipping_limit_date"]),
            price=to_dec(r["price"]), freight_value=to_dec(r["freight_value"])))

        self.load(Payment, d / "olist_order_payments_dataset.csv", lambda r: Payment(
            order_id=r["order_id"], sequential=int(r["payment_sequential"]),
            payment_type=r["payment_type"], installments=int(r["payment_installments"]),
            value=to_dec(r["payment_value"])))

        self.load(Review, d / "olist_order_reviews_dataset.csv", lambda r: Review(
            review_id=r["review_id"], order_id=r["order_id"], score=int(r["review_score"]),
            comment_title=s(r["review_comment_title"]), comment_message=s(r["review_comment_message"]),
            created_at=to_dt(r["review_creation_date"]), answered_at=to_dt(r["review_answer_timestamp"])))

        self.stdout.write(self.style.SUCCESS("Import terminé."))