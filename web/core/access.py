from django.db.models import Q

from .models import Order, Ticket


def orders_for(user):
    """Commandes visibles par cet utilisateur."""
    qs = Order.objects.select_related("customer").order_by("-purchased_at")
    if user.role == "vendeur":
        if not user.seller_id:
            return qs.none()
        return qs.filter(items__seller_id=user.seller_id).distinct()
    return qs


def tickets_for(user):
    """Tickets visibles par cet utilisateur."""
    qs = Ticket.objects.select_related("order", "created_by", "assigned_to")
    if user.role == "vendeur":
        cond = Q(created_by=user)
        if user.seller_id:
            cond |= Q(order__items__seller_id=user.seller_id)
        return qs.filter(cond).distinct()
    return qs