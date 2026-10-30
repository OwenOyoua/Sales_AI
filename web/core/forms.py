from django import forms
from django.forms import inlineformset_factory

from .access import orders_for
from .models import Customer, Order, OrderItem, Product, Ticket, User


class OrderCreateForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        label="Client",
        queryset=Customer.objects.all(),
        widget=forms.HiddenInput,
        error_messages={"required": "Sélectionnez un client dans les résultats."},
    )

    class Meta:
        model = Order
        fields = ["customer"]


class OrderItemCreateForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        label="Produit",
        queryset=Product.objects.all(),
        widget=forms.HiddenInput,
        error_messages={"required": "Sélectionnez un produit dans les résultats."},
    )
    price = forms.DecimalField(label="Prix", min_value=0, max_digits=10, decimal_places=2)
    freight_value = forms.DecimalField(label="Frais de livraison", min_value=0, max_digits=10, decimal_places=2, initial=0)

    class Meta:
        model = OrderItem
        fields = ["product", "price", "freight_value"]


OrderItemCreateFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemCreateForm,
    fields=["product", "price", "freight_value"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    max_num=10,
    validate_max=True,
)


class TicketForm(forms.ModelForm):
    order_ref = forms.CharField(label="ID de la commande", max_length=32, required=False)

    field_order = ["subject", "order_ref", "description", "priority", "status", "assigned_to"]

    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority", "status", "assigned_to"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance.pk:
            self.fields["order_ref"].initial = self.instance.order_id
        else:
            # À la création, statut et assignation restent par défaut
            del self.fields["status"]
            del self.fields["assigned_to"]
        if "assigned_to" in self.fields:
            self.fields["assigned_to"].queryset = User.objects.filter(role__in=["sav", "admin"])
        if user.role == "vendeur":
            self.fields["order_ref"].required = True

    def clean_order_ref(self):
        ref = self.cleaned_data["order_ref"].strip()
        if not ref:
            return None
        order = orders_for(self.user).filter(order_id=ref).first()
        if order is None:
            raise forms.ValidationError("Commande introuvable.")
        return order

    def save(self, commit=True):
        self.instance.order = self.cleaned_data.get("order_ref")
        return super().save(commit)
