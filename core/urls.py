from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('tickets/crear/', views.crear_ticket, name='crear_ticket'),
    path('tickets/', views.lista_tickets, name='lista_tickets'),
]