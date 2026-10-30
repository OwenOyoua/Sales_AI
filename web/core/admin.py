from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Customer,QueryLog, Order, Product, Seller, Ticket, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Rôle", {"fields": ("role", "seller")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Rôle", {"fields": ("role", "seller")}),)
    list_display = ("username", "email", "role", "seller", "is_active")
    list_filter = ("role", "is_active")
    raw_id_fields = ("seller",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "status", "purchased_at")
    list_filter = ("status",)
    search_fields = ("order_id",)
    raw_id_fields = ("customer",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "category_en")
    search_fields = ("product_id", "category_en")


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("seller_id", "city", "state")
    search_fields = ("seller_id", "city")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "city", "state")
    search_fields = ("customer_id", "city")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "status", "priority", "assigned_to", "created_at")
    list_filter = ("status", "priority")
    raw_id_fields = ("order",)



@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "question", "status", "duration_ms", "feedback", "via_voice", "created_at")
    list_filter = ("status", "feedback", "via_voice", "user__role")
    search_fields = ("question", "sql")
    readonly_fields = [f.name for f in QueryLog._meta.fields]