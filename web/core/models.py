from django.contrib.auth.models import AbstractUser
from django.db import models


class Customer(models.Model):
    customer_id = models.CharField(max_length=32, primary_key=True)
    customer_unique_id = models.CharField(max_length=32, db_index=True)
    zip_code_prefix = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)

    class Meta:
        db_table = "customers"

    def __str__(self):
        return f"{self.customer_id[:8]} ({self.city})"


class Seller(models.Model):
    seller_id = models.CharField(max_length=32, primary_key=True)
    zip_code_prefix = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)

    class Meta:
        db_table = "sellers"

    def __str__(self):
        return f"{self.seller_id[:8]} ({self.city})"


class Product(models.Model):
    product_id = models.CharField(max_length=32, primary_key=True)
    category = models.CharField(max_length=100, blank=True)      # en portugais
    category_en = models.CharField(max_length=100, blank=True)   # traduction
    name_length = models.IntegerField(null=True, blank=True)
    description_length = models.IntegerField(null=True, blank=True)
    photos_qty = models.IntegerField(null=True, blank=True)
    weight_g = models.IntegerField(null=True, blank=True)
    length_cm = models.IntegerField(null=True, blank=True)
    height_cm = models.IntegerField(null=True, blank=True)
    width_cm = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "products"

    def __str__(self):
        return f"{self.product_id[:8]} ({self.category_en or self.category})"


class Order(models.Model):
    order_id = models.CharField(max_length=32, primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, db_column="customer_id")
    status = models.CharField(max_length=20, db_index=True)
    purchased_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return self.order_id[:8]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column="order_id", related_name="items")
    item_number = models.IntegerField()
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_column="product_id")
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, db_column="seller_id")
    shipping_limit_at = models.DateTimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    freight_value = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        unique_together = [("order", "item_number")]


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column="order_id", related_name="payments")
    sequential = models.IntegerField()
    payment_type = models.CharField(max_length=20)
    installments = models.IntegerField()
    value = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_payments"


class Review(models.Model):
    review_id = models.CharField(max_length=32, db_index=True)  # pas unique dans Olist
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column="order_id", related_name="reviews")
    score = models.IntegerField()
    comment_title = models.CharField(max_length=255, blank=True)
    comment_message = models.TextField(blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order_reviews"


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        DIRECTEUR = "directeur", "Directeur"
        VENDEUR = "vendeur", "Vendeur"
        SAV = "sav", "Service après-vente"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VENDEUR)
    seller = models.ForeignKey(Seller, null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        IN_PROGRESS = "in_progress", "En cours"
        RESOLVED = "resolved", "Résolu"
        CLOSED = "closed", "Fermé"

    class Priority(models.TextChoices):
        LOW = "low", "Basse"
        NORMAL = "normal", "Normale"
        HIGH = "high", "Haute"

    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    subject = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="tickets_created")
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets_assigned")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.subject}"



class QueryLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="queries")
    question = models.TextField()
    answer = models.TextField(blank=True)
    sql = models.TextField(blank=True)
    columns = models.JSONField(default=list)
    rows = models.JSONField(default=list)   # 50 premières lignes seulement
    status = models.CharField(max_length=15, db_index=True)  # ok, impossible, error
    duration_ms = models.IntegerField(default=0)
    feedback = models.SmallIntegerField(null=True, blank=True)  # 1 = 👍, -1 = 👎
    via_voice = models.BooleanField(default=False)  # servira pour le speech to text
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.question[:40]}"