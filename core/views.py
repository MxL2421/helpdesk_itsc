# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import TicketForm, ActualizarTicketForm, LoginForm, ReasignarTicketForm, AdjuntoFormSet,  EtiquetarMaestroForm
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib import messages
from .models import Ticket, HistorialTicket, TicketEtiquetado


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
                messages.success(request, f'{maestro.get_full_name()} fue etiquetado correctamente.')

            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = EtiquetarMaestroForm()

    return render(request, 'tickets/etiquetar.html', {'form': form, 'ticket': ticket})

@login_required
def lista_tickets(request):
    if request.user.rol in ['administrador', 'tecnico']:
        tickets = Ticket.objects.all()
    else:
        tickets = Ticket.objects.filter(creador=request.user)

    return render(request, 'tickets/lista.html', {'tickets': tickets})

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

    return render(request, 'tickets/detalle.html', {'ticket': ticket})


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
    if request.method != 'POST':
        return HttpResponseForbidden('Método no permitido.')

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.user.rol != 'tecnico':
        return HttpResponseForbidden('Solo los técnicos pueden autoasignarse tickets.')

    if ticket.tecnico is not None:
        messages.error(request, 'Este ticket ya tiene un técnico asignado.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    ticket.tecnico = request.user
    ticket.save()

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

            messages.success(request, 'Técnico reasignado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ReasignarTicketForm(instance=ticket)

    return render(request, 'tickets/reasignar.html', {'form': form, 'ticket': ticket})


# Controla el Logout

def logout_view(request):
    logout(request)
    return redirect('login')