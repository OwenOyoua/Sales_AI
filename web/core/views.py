import json
import uuid


import httpx
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)
from . import stats

from .access import orders_for, tickets_for
from .forms import OrderCreateForm, OrderItemCreateFormSet, TicketForm
from .models import Customer, Order, Product, QueryLog, Ticket
from .permissions import RoleRequiredMixin

ALL_ROLES = ("admin", "directeur", "vendeur", "sav")
STATUSES = ["created", "approved", "invoiced", "processing", "shipped",
            "delivered", "canceled", "unavailable"]


@login_required
def home(request):
    return redirect("orders")


# ---------- Commandes ----------

class OrderCreateView(RoleRequiredMixin, View):
    allowed_roles = ("vendeur",)
    template_name = "core/order_form.html"

    def get(self, request):
        return self.render_form(OrderCreateForm(), OrderItemCreateFormSet(instance=Order(), prefix="items"))

    def post(self, request):
        form = OrderCreateForm(request.POST)
        item_formset = OrderItemCreateFormSet(request.POST, instance=Order(), prefix="items")
        if not request.user.seller_id:
            form.add_error(None, "Votre compte n'est associé à aucun vendeur. Contactez un administrateur.")
            return self.render_form(form, item_formset)
        form_is_valid = form.is_valid()
        items_are_valid = item_formset.is_valid()
        if form_is_valid and items_are_valid:
            with transaction.atomic():
                order = form.save(commit=False)
                order.order_id = uuid.uuid4().hex
                order.status = "created"
                order.purchased_at = timezone.now()
                order.save()

                item_formset.instance = order
                for item_number, item in enumerate(item_formset.save(commit=False), start=1):
                    item.order = order
                    item.seller_id = request.user.seller_id
                    item.item_number = item_number
                    item.save()
            return redirect("order_detail", pk=order.pk)
        return self.render_form(form, item_formset)

    def render_form(self, form, item_formset):
        return render(self.request, self.template_name, {
            "form": form,
            "item_formset": item_formset,
            "customer_search_url": reverse("order_customer_search"),
            "product_search_url": reverse("order_product_search"),
        })

@login_required
@require_GET
def order_customer_search(request):
    if request.user.role != "vendeur" or not request.user.seller_id:
        return JsonResponse({"error": "Accès refusé."}, status=403)
    query = request.GET.get("q", "").strip()
    if len(query) == 1:
        return JsonResponse([], safe=False)
    customers = Customer.objects.all()
    if query:
        customers = customers.filter(
            Q(customer_id__istartswith=query)
            | Q(customer_unique_id__istartswith=query)
            | Q(zip_code_prefix__istartswith=query)
            | Q(city__icontains=query)
            | Q(state__iexact=query)
        )
    customers = customers.order_by("city", "customer_id")[:12]
    return JsonResponse([
        {
            "id": customer.pk,
            "name": f"{customer.city} ({customer.state})",
            "detail": f"CEP {customer.zip_code_prefix} · Client {customer.customer_id[:8]}",
            "label": f"{customer.city} ({customer.state}) · {customer.customer_id[:8]}",
        }
        for customer in customers
    ], safe=False)


@login_required
@require_GET
def order_product_search(request):
    if request.user.role != "vendeur" or not request.user.seller_id:
        return JsonResponse({"error": "Accès refusé."}, status=403)
    query = request.GET.get("q", "").strip()
    if len(query) == 1:
        return JsonResponse([], safe=False)
    products = Product.objects.all()
    if query:
        products = products.filter(
            Q(product_id__istartswith=query) | Q(category_en__icontains=query) | Q(category__icontains=query)
        )
    products = products.order_by("category_en", "product_id")[:12]
    return JsonResponse([
        _product_lookup_entry(product)
        for product in products
    ], safe=False)


def _product_lookup_entry(product):
    details = [f"Réf. {product.product_id[:8]}"]
    if product.weight_g is not None:
        details.append(f"{product.weight_g} g")
    dimensions = [value for value in (product.length_cm, product.height_cm, product.width_cm) if value is not None]
    if dimensions:
        details.append(f"{' × '.join(str(value) for value in dimensions)} cm")
    name = product.category_en or product.category or "Produit"
    return {
        "id": product.pk,
        "name": name,
        "detail": " · ".join(details),
        "label": f"{name} · {product.product_id[:8]}",
    }

class OrderListView(RoleRequiredMixin, ListView):
    allowed_roles = ALL_ROLES
    template_name = "core/order_list.html"
    paginate_by = 25

    def get_queryset(self):
        qs = orders_for(self.request.user)
        status = self.request.GET.get("status")
        q = self.request.GET.get("q", "").strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(order_id__startswith=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = STATUSES
        return ctx


class OrderDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = ALL_ROLES
    template_name = "core/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return orders_for(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        items = self.object.items.select_related("product", "seller")
        if user.role == "vendeur":
            items = items.filter(seller_id=user.seller_id)
        ctx["items"] = items
        ctx["total"] = sum(i.price + i.freight_value for i in items)
        return ctx


# ---------- Tickets ----------

class TicketListView(RoleRequiredMixin, ListView):
    allowed_roles = ALL_ROLES
    template_name = "core/ticket_list.html"
    paginate_by = 25

    def get_queryset(self):
        qs = tickets_for(self.request.user)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = Ticket.Status.choices
        return ctx


class TicketDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = ALL_ROLES
    template_name = "core/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        return tickets_for(self.request.user)


class TicketCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = ("admin", "sav", "vendeur")
    form_class = TicketForm
    template_name = "core/ticket_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ticket_detail", args=[self.object.pk])


class TicketUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = ("admin", "sav")
    form_class = TicketForm
    template_name = "core/ticket_form.html"

    def get_queryset(self):
        return tickets_for(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("ticket_detail", args=[self.object.pk])


class TicketDeleteView(RoleRequiredMixin, DeleteView):
    allowed_roles = ("admin",)
    template_name = "core/ticket_confirm_delete.html"
    success_url = reverse_lazy("tickets")
    context_object_name = "ticket"

    def get_queryset(self):
        return tickets_for(self.request.user)



# ---------- Assistant IA ----------

@login_required
def chat(request):
    history = QueryLog.objects.filter(user=request.user)[:10]
    return render(request, "core/chat.html", {"history": history})


@login_required
@require_POST
def ask_view(request):
    user = request.user
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "Requête invalide."}, status=400)
    question = str(data.get("question", "")).strip()
    via_voice = bool(data.get("via_voice", False))
    if not 3 <= len(question) <= 500:
        return JsonResponse({"error": "La question doit faire entre 3 et 500 caractères."}, status=400)
    if user.role == "vendeur" and not user.seller_id:
        return JsonResponse({"error": "Votre compte n'est lié à aucun vendeur. Contactez un administrateur."}, status=400)

    try:
        r = httpx.post(
            f"{settings.AI_SERVICE_URL}/ask",
            json={"question": question, "role": user.role, "seller_id": user.seller_id or ""},
            headers={"X-Internal-Token": settings.AI_INTERNAL_TOKEN},
            timeout=120,
        )
        r.raise_for_status()
        p = r.json()
    except httpx.TimeoutException:
        p = {"status": "error", "answer": "Le service met trop de temps à répondre. Réessayez.",
             "sql": "", "columns": [], "rows": [], "duration_ms": 0}
    except (httpx.HTTPError, ValueError):
        p = {"status": "error", "answer": "Le service IA est indisponible pour le moment.",
             "sql": "", "columns": [], "rows": [], "duration_ms": 0}

    log = QueryLog.objects.create(
        user=user, question=question, answer=p["answer"], sql=p["sql"],
        columns=p["columns"], rows=p["rows"][:50], status=p["status"],
        duration_ms=p["duration_ms"], via_voice=via_voice,
    )
    p["log_id"] = log.pk
    # Le vendeur ne voit pas le SQL ; les autres rôles, oui
    if user.role == "vendeur":
        p["sql"] = ""
    return JsonResponse(p)


@login_required
@require_POST
def feedback_view(request, pk):
    log = get_object_or_404(QueryLog, pk=pk, user=request.user)
    try:
        value = int(json.loads(request.body).get("value"))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "Valeur invalide."}, status=400)
    if value not in (1, -1):
        return JsonResponse({"error": "Valeur invalide."}, status=400)
    log.feedback = value
    log.save(update_fields=["feedback"])
    return JsonResponse({"ok": True})



# ---------- Dashboard ----------

@login_required
def dashboard_view(request):
    user = request.user
    raw = request.GET.get("year", "")
    year = int(raw) if raw in ("2016", "2017", "2018") else None  # toute autre valeur : ignorée

    ctx = {"year": year, "years": [2016, 2017, 2018], "kind": "none"}
    if user.role == "sav":
        ctx.update(stats.sav_data(year))
    elif user.role == "vendeur":
        if user.seller_id:
            ctx.update(stats.sales_data(year, user.seller_id))
    else:
        ctx.update(stats.sales_data(year))
    if user.role in ("admin", "directeur"):
        ctx["ai"] = stats.ai_usage()
    return render(request, "core/dashboard.html", ctx)
