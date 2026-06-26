from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('tickets/crear/', views.crear_ticket, name='crear_ticket'),
    path('tickets/', views.lista_tickets, name='lista_tickets'),
    path('tickets/<int:ticket_id>/', views.detalle_ticket, name='detalle_ticket'),
    path('tickets/<int:ticket_id>/autoasignar/', views.autoasignar_ticket, name='autoasignar_ticket'),
    path('tickets/<int:ticket_id>/actualizar/', views.actualizar_ticket, name='actualizar_ticket'),
    path('tickets/<int:ticket_id>/reabrir/', views.reabrir_ticket, name='reabrir_ticket'),
]