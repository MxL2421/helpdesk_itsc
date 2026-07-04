# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from .forms import TicketForm, ActualizarTicketForm, LoginForm, ReasignarTicketForm, AdjuntoFormSet, EtiquetarMaestroForm, RedirigirTicketForm, ComentarioForm
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib import messages
from .models import Ticket, HistorialTicket, TicketEtiquetado, Comentario, Notificacion
from django.core.mail import send_mail


def inicio(request):
    return render(request, 'inicio.html')

@login_required
def crear_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.creador = request.user
            ticket.save()

            formset = AdjuntoFormSet(request.POST, request.FILES, instance=ticket)
            if formset.is_valid():
                for adjunto_form in formset:
                    if adjunto_form.cleaned_data.get('ruta'):
                        adjunto = adjunto_form.save(commit=False)
                        adjunto.ticket = ticket
                        adjunto.nombre_archivo = adjunto.ruta.name
                        adjunto.tipo_mime = adjunto.ruta.file.content_type if hasattr(adjunto.ruta.file, 'content_type') else 'desconocido'
                        adjunto.save()

            enviar_notificacion(
                ticket=ticket,
                destinatario_correo=ticket.creador.correo,
                asunto=f'Ticket #{ticket.id} creado: {ticket.titulo}',
                mensaje=f'Hola {ticket.creador.nombre},\n\nTu ticket "{ticket.titulo}" fue creado correctamente.\n\nCategoría: {ticket.categoria}\n\nPuedes hacerle seguimiento desde el sistema.'
            )

            return redirect('lista_tickets')
    else:
        form = TicketForm()
        formset = AdjuntoFormSet()

    return render(request, 'tickets/crear.html', {'form': form, 'formset': formset})

@login_required
def etiquetar_maestro(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user

    es_creador = ticket.creador == user
    es_tecnico_o_admin = user.rol in ['tecnico', 'administrador']

    if not (es_creador or es_tecnico_o_admin):
        return HttpResponseForbidden('No tienes permiso para etiquetar maestros en este ticket.')

    if request.method == 'POST':
        form = EtiquetarMaestroForm(request.POST)
        if form.is_valid():
            maestro = form.cleaned_data['maestro']

            ya_etiquetado = TicketEtiquetado.objects.filter(ticket=ticket, usuario=maestro).exists()
            if ya_etiquetado:
                messages.error(request, 'Este maestro ya está etiquetado en el ticket.')
            else:
                TicketEtiquetado.objects.create(ticket=ticket, usuario=maestro)

                enviar_notificacion(
                    ticket=ticket,
                    destinatario_correo=maestro.correo,
                    asunto=f'Has sido etiquetado en el ticket #{ticket.id}',
                    mensaje=f'Hola {maestro.nombre},\n\nFuiste etiquetado como observador en el ticket "{ticket.titulo}".\n\nPuedes consultar los detalles del ticket desde el sistema.'
                )

                messages.success(request, f'{maestro.get_full_name()} fue etiquetado correctamente.')

            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = EtiquetarMaestroForm()

    return render(request, 'tickets/etiquetar.html', {'form': form, 'ticket': ticket})

def enviar_notificacion(ticket, destinatario_correo, asunto, mensaje):
    notificacion = Notificacion.objects.create(
        asunto=asunto,
        mensaje=mensaje,
        correo_destino=destinatario_correo,
        ticket=ticket
    )

    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=None,
            recipient_list=[destinatario_correo],
            fail_silently=False,
        )
        notificacion.enviada = True
        notificacion.fecha_envio = timezone.now()
        notificacion.save()
    except Exception:
        pass

@login_required
def lista_tickets(request):
    if request.user.rol in ['administrador', 'tecnico']:
        tickets = Ticket.objects.all()
    else:
        tickets = Ticket.objects.filter(creador=request.user)

    # Filtro por prioridad
    prioridad = request.GET.get('prioridad')
    if prioridad in ['baja', 'media', 'alta']:
        tickets = tickets.filter(prioridad=prioridad)

    # Filtro por tiempo de duración
    duracion = request.GET.get('duracion')
    if duracion == 'hoy':
        tickets = tickets.filter(fecha_creacion__date=timezone.now().date())
    elif duracion == 'semana':
        tickets = tickets.filter(fecha_creacion__gte=timezone.now() - timedelta(days=7))
    elif duracion == 'mes':
        tickets = tickets.filter(fecha_creacion__gte=timezone.now() - timedelta(days=30))

    return render(request, 'tickets/lista.html', {
        'tickets': tickets,
        'prioridad_actual': prioridad,
        'duracion_actual': duracion,
    })

# Verificar que el ticket existe y quien abre el enlace sea un usuario etiquetado, admin o técnico
@login_required
def detalle_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user

    es_creador = ticket.creador == user
    es_tecnico_o_admin = user.rol in ['tecnico', 'administrador']
    esta_etiquetado = ticket.ticketetiquetado_set.filter(usuario=user).exists()

    if not (es_creador or es_tecnico_o_admin or esta_etiquetado):
        return HttpResponseForbidden('No tienes permiso para ver este ticket.')

    es_tecnico_asignado_o_admin = (ticket.tecnico == user) or (user.rol == 'administrador')

    if request.method == 'POST':
        form = ComentarioForm(request.POST)
        if form.is_valid():
            comentario = form.save(commit=False)
            comentario.ticket = ticket
            comentario.autor = user

            if comentario.es_privado and not es_tecnico_asignado_o_admin:
                messages.error(request, 'No tienes permiso para escribir comentarios privados.')
                return redirect('detalle_ticket', ticket_id=ticket.id)

            comentario.save()
            messages.success(request, 'Comentario agregado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ComentarioForm()

    if es_tecnico_asignado_o_admin:
        comentarios = ticket.comentarios.all()
    else:
        comentarios = ticket.comentarios.filter(es_privado=False)

    return render(request, 'tickets/detalle.html', {
        'ticket': ticket,
        'form': form,
        'comentarios': comentarios,
    })


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if user.rol == 'administrador':
                return redirect('/admin/')
            else:
                return redirect('lista_tickets')
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form})

# Un ticket solo puede tomarlo un técnico si este no ha sido asignado
@login_required
def autoasignar_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method != 'POST':
        return HttpResponseForbidden('Método no permitido.')

    if request.user.rol != 'tecnico':
        return HttpResponseForbidden('Solo los técnicos pueden autoasignarse tickets.')

    if ticket.tecnico is not None:
        messages.error(request, 'Este ticket ya tiene un técnico asignado.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    ticket.tecnico = request.user
    ticket.save()

    enviar_notificacion(
        ticket=ticket,
        destinatario_correo=ticket.tecnico.correo,
        asunto=f'Te has autoasignado el ticket #{ticket.id}',
        mensaje=f'Hola {ticket.tecnico.nombre},\n\nTe has autoasignado el ticket "{ticket.titulo}".\n\nCategoría: {ticket.categoria}\nPrioridad: {ticket.prioridad or "Sin asignar"}'
    )

    messages.success(request, 'Te has autoasignado el ticket correctamente.')
    return redirect('detalle_ticket', ticket_id=ticket.id)


# Solo el técnico asignado puede actualizar la prioridad y el estado del ticket

@login_required
def actualizar_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.tecnico != request.user:
        return HttpResponseForbidden('Solo el técnico asignado puede actualizar este ticket.')

    if ticket.estado == 'cerrado':
        messages.error(request, 'No se puede modificar un ticket cerrado. Pide al administrador que lo reabra.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    if request.method == 'POST':
        estado_anterior = ticket.estado
        prioridad_anterior = ticket.prioridad

        form = ActualizarTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket_actualizado = form.save(commit=False)

            if estado_anterior != ticket_actualizado.estado and ticket_actualizado.estado == 'cerrado':
                ticket_actualizado.fecha_cierre = timezone.now()

            ticket_actualizado.save()

            if estado_anterior != ticket_actualizado.estado:
                HistorialTicket.objects.create(
                    campo='estado',
                    valor_anterior=estado_anterior,
                    valor_nuevo=ticket_actualizado.estado,
                    ticket=ticket_actualizado,
                    usuario=request.user
                )

            if prioridad_anterior != ticket_actualizado.prioridad:
                HistorialTicket.objects.create(
                    campo='prioridad',
                    valor_anterior=prioridad_anterior,
                    valor_nuevo=ticket_actualizado.prioridad,
                    ticket=ticket_actualizado,
                    usuario=request.user
                )

            enviar_notificacion(
                ticket=ticket_actualizado,
                destinatario_correo=ticket_actualizado.creador.correo,
                asunto=f'Ticket #{ticket_actualizado.id} actualizado',
                mensaje=f'Hola {ticket_actualizado.creador.nombre},\n\nTu ticket "{ticket_actualizado.titulo}" fue actualizado.\n\nEstado: {ticket_actualizado.get_estado_display()}\nPrioridad: {ticket_actualizado.prioridad or "Sin asignar"}'
            )

            messages.success(request, 'Ticket actualizado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ActualizarTicketForm(instance=ticket)

    return render(request, 'tickets/actualizar.html', {'form': form, 'ticket': ticket})

# Solo el administrador puede reabrir tickets y solo se pueden reabrir tickets 
@login_required
def reabrir_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Solo el administrador puede reabrir tickets.')

    if request.method != 'POST':
        return HttpResponseForbidden('Método no permitido.')

    if ticket.estado != 'cerrado':
        messages.error(request, 'Solo se pueden reabrir tickets cerrados.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    ultimo_cambio_estado = HistorialTicket.objects.filter(
        ticket=ticket,
        campo='estado'
    ).order_by('-fecha').first()

    estado_anterior = ultimo_cambio_estado.valor_anterior if ultimo_cambio_estado else 'nuevo'

    estado_cerrado = ticket.estado
    ticket.estado = estado_anterior
    ticket.fecha_cierre = None
    ticket.save()

    HistorialTicket.objects.create(
        campo='estado',
        valor_anterior=estado_cerrado,
        valor_nuevo=estado_anterior,
        ticket=ticket,
        usuario=request.user
    )

    messages.success(request, f'Ticket reabierto, vuelve al estado: {ticket.get_estado_display()}.')
    return redirect('detalle_ticket', ticket_id=ticket.id)

# Solo el admin puede reasignar tickets

@login_required
def reasignar_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Solo el administrador puede reasignar tickets.')

    tecnico_anterior = ticket.tecnico

    if request.method == 'POST':
        form = ReasignarTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket_actualizado = form.save()

            if tecnico_anterior != ticket_actualizado.tecnico:
                HistorialTicket.objects.create(
                    campo='tecnico',
                    valor_anterior=str(tecnico_anterior) if tecnico_anterior else 'Sin asignar',
                    valor_nuevo=str(ticket_actualizado.tecnico) if ticket_actualizado.tecnico else 'Sin asignar',
                    ticket=ticket_actualizado,
                    usuario=request.user
                )

                if ticket_actualizado.tecnico:
                    enviar_notificacion(
                        ticket=ticket_actualizado,
                        destinatario_correo=ticket_actualizado.tecnico.correo,
                        asunto=f'Se te asignó el ticket #{ticket_actualizado.id}',
                        mensaje=f'Hola {ticket_actualizado.tecnico.nombre},\n\nEl administrador te ha asignado el ticket "{ticket_actualizado.titulo}".\n\nCategoría: {ticket_actualizado.categoria}\nPrioridad: {ticket_actualizado.prioridad or "Sin asignar"}'
                    )

            messages.success(request, 'Técnico reasignado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ReasignarTicketForm(instance=ticket)

    return render(request, 'tickets/reasignar.html', {'form': form, 'ticket': ticket})
@login_required
def redirigir_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user

    es_tecnico_asignado = user.rol == 'tecnico' and ticket.tecnico == user
    es_admin = user.rol == 'administrador'

    if not (es_tecnico_asignado or es_admin):
        return HttpResponseForbidden('No tienes permiso para redirigir este ticket.')

    if ticket.estado == 'cerrado':
        messages.error(request, 'No se puede redirigir un ticket cerrado.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    if request.method == 'POST':
        categoria_anterior = ticket.categoria
        form = RedirigirTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket_actualizado = form.save()

            if categoria_anterior != ticket_actualizado.categoria:
                HistorialTicket.objects.create(
                    campo='categoria',
                    valor_anterior=str(categoria_anterior),
                    valor_nuevo=str(ticket_actualizado.categoria),
                    ticket=ticket_actualizado,
                    usuario=request.user
                )

            messages.success(request, 'Ticket redirigido correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = RedirigirTicketForm(instance=ticket)

    return render(request, 'tickets/redirigir.html', {'form': form, 'ticket': ticket})


# Controla el Logout

def logout_view(request):
    logout(request)
    return redirect('login')