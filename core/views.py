# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import TicketForm
from .models import Ticket
from django.contrib.auth import login, logout
from .forms import LoginForm


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


def logout_view(request):
    logout(request)
    return redirect('login')