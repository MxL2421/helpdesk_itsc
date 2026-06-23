# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import TicketForm
from .models import Ticket
from django.contrib.auth import login, logout
from .forms import LoginForm
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib import messages



@login_required
def crear_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.creador = request.user
            ticket.save()
            return redirect('lista_tickets')
    else:
        form = TicketForm()

    return render(request, 'tickets/crear.html', {'form': form})


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


# Controla el Logout

def logout_view(request):
    logout(request)
    return redirect('login')