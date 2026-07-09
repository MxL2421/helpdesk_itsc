from django.urls import path
from . import views


urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil, name='perfil'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('tickets/crear/', views.crear_ticket, name='crear_ticket'),
    path('tickets/', views.lista_tickets, name='lista_tickets'),
    path('tickets/<int:ticket_id>/', views.detalle_ticket, name='detalle_ticket'),
    path('tickets/<int:ticket_id>/autoasignar/', views.autoasignar_ticket, name='autoasignar_ticket'),
    path('tickets/<int:ticket_id>/actualizar/', views.actualizar_ticket, name='actualizar_ticket'),
    path('tickets/<int:ticket_id>/reasignar/', views.reasignar_ticket, name='reasignar_ticket'),
    path('tickets/<int:ticket_id>/reabrir/', views.reabrir_ticket, name='reabrir_ticket'),
    path('tickets/<int:ticket_id>/etiquetar/', views.etiquetar_maestro, name='etiquetar_maestro'),
    path('tickets/<int:ticket_id>/redirigir/', views.redirigir_ticket, name='redirigir_ticket'),
    path('panel/usuarios/', views.admin_usuarios, name='admin_usuarios'),
    path('panel/usuarios/crear/', views.admin_crear_usuario, name='admin_crear_usuario'),
    path('panel/usuarios/<int:usuario_id>/editar/', views.admin_editar_usuario, name='admin_editar_usuario'),
    path('panel/usuarios/<int:usuario_id>/eliminar/', views.admin_eliminar_usuario, name='admin_eliminar_usuario'),
    path('panel/categorias/', views.admin_categorias, name='admin_categorias'),
    path('panel/categorias/crear/', views.admin_crear_categoria, name='admin_crear_categoria'),
    path('panel/categorias/<int:categoria_id>/editar/', views.admin_editar_categoria, name='admin_editar_categoria'),
    path('panel/categorias/<int:categoria_id>/eliminar/', views.admin_eliminar_categoria, name='admin_eliminar_categoria'),
    path('panel/usuarios/<int:usuario_id>/toggle/', views.admin_toggle_usuario, name='admin_toggle_usuario'),
    path('panel/notificaciones/', views.admin_notificaciones, name='admin_notificaciones'),
    path('logout/', views.logout_view, name='logout'),
]