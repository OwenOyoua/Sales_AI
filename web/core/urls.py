from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("orders/", views.OrderListView.as_view(), name="orders"),
    path("orders/new/", views.OrderCreateView.as_view(), name="order_new"),
    path("orders/customer-search/", views.order_customer_search, name="order_customer_search"),
    path("orders/product-search/", views.order_product_search, name="order_product_search"),
    path("orders/<str:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("tickets/", views.TicketListView.as_view(), name="tickets"),
    path("tickets/new/", views.TicketCreateView.as_view(), name="ticket_new"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("tickets/<int:pk>/edit/", views.TicketUpdateView.as_view(), name="ticket_edit"),
    path("tickets/<int:pk>/delete/", views.TicketDeleteView.as_view(), name="ticket_delete"),
    path("chat/", views.chat, name="chat"),
    path("chat/ask/", views.ask_view, name="chat_ask"),
    path("chat/feedback/<int:pk>/", views.feedback_view, name="chat_feedback"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]
