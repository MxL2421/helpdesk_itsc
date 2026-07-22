from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import models as django_models
from django.db import models as db_models
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.core.mail import send_mail
import os
from django.utils import timezone
from datetime import timedelta

from .forms import (
    TicketForm, ActualizarTicketForm, LoginForm,
    AdjuntoFormSet, ReasignarTicketForm, EtiquetarMaestroForm,
    RedirigirTicketForm, ComentarioForm, CambiarContrasenaForm, 
    CrearUsuarioForm, EditarUsuarioForm, ConfirmarPasswordForm,
    CategoriaForm, EliminarCategoriaForm, AreaForm
)
from .models import (
    Ticket, HistorialTicket, TicketEtiquetado, Comentario, Notificacion,
    Usuario, Categoria, Area
)


# ─── FUNCIONES AUXILIARES ────────────────────────────────────────

def enviar_notificacion(ticket, destinatario_correo, asunto, mensaje, destinatario_usuario=None):
    notificacion = Notificacion.objects.create(
        asunto=asunto,
        mensaje=mensaje,
        correo_destino=destinatario_correo,
        ticket=ticket,
        destinatario=destinatario_usuario
    )

    es_estudiante = destinatario_usuario and destinatario_usuario.rol == 'estudiante'

    if es_estudiante:
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
    else:
        notificacion.enviada = True
        notificacion.fecha_envio = timezone.now()
        notificacion.save()

def calcular_fecha_limite(ticket):
    TIEMPOS = {
        'alta': timedelta(hours=24),
        'media': timedelta(hours=48),
        'baja': timedelta(hours=72),
    }
    if ticket.prioridad and ticket.prioridad in TIEMPOS:
        return ticket.fecha_creacion + TIEMPOS[ticket.prioridad]
    return None


# ─── INICIO ────────────────────────────────────────────────────────────────────

def inicio(request):
    return render(request, 'inicio.html')


# ─── AUTENTICACIÓN ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.rol in ['administrador', 'tecnico']:
                return redirect('dashboard')
            else:
                return redirect('lista_tickets')
    else:
        form = LoginForm()
    return render(request, 'auth/login.html', {'form': form})

@login_required
def perfil(request):
    if request.method == 'POST':
        form = CambiarContrasenaForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Contraseña cambiada correctamente.')
            return redirect('perfil')
    else:
        form = CambiarContrasenaForm(request.user)

    return render(request, 'perfil.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── NOTIFICACIONES ────────────────────────────────────────────────────────────

@login_required
def notificaciones(request):
    notifs = list(Notificacion.objects.filter(
        destinatario=request.user,
        leida=False
    ).order_by('-fecha_envio'))

    Notificacion.objects.filter(
        destinatario=request.user,
        leida=False
    ).update(leida=True)

    return render(request, 'notificaciones.html', {'notificaciones': notifs})

@login_required
def admin_notificaciones(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    notificaciones = Notificacion.objects.all().order_by('-fecha_envio')

    busqueda = request.GET.get('q')
    if busqueda:
        notificaciones = notificaciones.filter(
            Q(asunto__icontains=busqueda) |
            Q(correo_destino__icontains=busqueda)
        )

    enviada = request.GET.get('enviada')
    if enviada == 'si':
        notificaciones = notificaciones.filter(enviada=True)
    elif enviada == 'no':
        notificaciones = notificaciones.filter(enviada=False)

    return render(request, 'admin/notificaciones.html', {
        'notificaciones': notificaciones,
        'busqueda_actual': busqueda,
        'enviada_actual': enviada,
    })


# ─── TICKETS ───────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if request.user.rol not in ['administrador', 'tecnico']:
        return HttpResponseForbidden('No tienes permiso para ver el dashboard.')

    ahora = timezone.now()

    if request.user.rol == 'tecnico':
        areas = request.user.areas.all()
        if areas.exists():
            tickets_base = Ticket.objects.filter(categoria__area__in=areas)
        else:
            tickets_base = Ticket.objects.none()
    else:
        tickets_base = Ticket.objects.all()

    # ── ESTADÍSTICAS ADMINISTRADOR ──────────────────────────────────────────
    if request.user.rol == 'administrador':
        from django.db.models.functions import TruncMonth
        from django.db.models import Count, F
        import json

        total = tickets_base.count()
        abiertos = tickets_base.filter(estado__in=['nuevo', 'en_revision', 'en_progreso']).count()
        cerrados = tickets_base.filter(estado='cerrado').count()
        total_usuarios = Usuario.objects.filter(is_active=True).count()

        estados = {
            'Nuevo': tickets_base.filter(estado='nuevo').count(),
            'En revisión': tickets_base.filter(estado='en_revision').count(),
            'En progreso': tickets_base.filter(estado='en_progreso').count(),
            'Desestimado': tickets_base.filter(estado='desestimado').count(),
            'Cerrado': tickets_base.filter(estado='cerrado').count(),
        }

        areas_data = {}
        for area in Area.objects.all():
            areas_data[area.nombre] = tickets_base.filter(categoria__area=area).count()

        urgencia = {
            'Alta': tickets_base.filter(prioridad='alta').count(),
            'Media': tickets_base.filter(prioridad='media').count(),
            'Baja': tickets_base.filter(prioridad='baja').count(),
            'Sin asignar': tickets_base.filter(prioridad__isnull=True).count(),
        }

        tickets_con_limite = tickets_base.filter(fecha_limite__isnull=False)
        total_sla = tickets_con_limite.count()
        cumplieron_sla = tickets_con_limite.filter(
            estado='cerrado',
            fecha_cierre__lte=F('fecha_limite')
        ).count()
        no_cumplieron_sla = tickets_con_limite.filter(
            estado='cerrado',
            fecha_cierre__gt=F('fecha_limite')
        ).count()
        expirados_abiertos = tickets_con_limite.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__lt=ahora
        ).count()

        sla = {
            'Cumplido': cumplieron_sla,
            'Incumplido': no_cumplieron_sla,
            'Expirado abierto': expirados_abiertos,
        }

        porcentaje_sla = round((cumplieron_sla / total_sla * 100), 1) if total_sla > 0 else 0

        creados_por_mes = list(
            tickets_base
            .annotate(mes=TruncMonth('fecha_creacion'))
            .values('mes')
            .annotate(total=Count('id'))
            .order_by('mes')[:6]
        )

        resueltos_por_mes = list(
            tickets_base.filter(estado='cerrado', fecha_cierre__isnull=False)
            .annotate(mes=TruncMonth('fecha_cierre'))
            .values('mes')
            .annotate(total=Count('id'))
            .order_by('mes')[:6]
        )

        meses_labels = [c['mes'].strftime('%b %Y') for c in creados_por_mes if c['mes']]
        creados_data = [c['total'] for c in creados_por_mes]
        resueltos_dict = {r['mes'].strftime('%b %Y'): r['total'] for r in resueltos_por_mes if r['mes']}
        resueltos_data = [resueltos_dict.get(m, 0) for m in meses_labels]

        tecnicos_stats = []
        for tecnico in Usuario.objects.filter(rol='tecnico', is_active=True):
            asignados = tickets_base.filter(tecnico=tecnico).count()
            resueltos = tickets_base.filter(tecnico=tecnico, estado='cerrado').count()
            if asignados > 0:
                tecnicos_stats.append({
                    'nombre': tecnico.get_full_name(),
                    'asignados': asignados,
                    'resueltos': resueltos,
                })

        tecnicos_nombres = json.dumps([t['nombre'] for t in tecnicos_stats])
        tecnicos_asignados = json.dumps([t['asignados'] for t in tecnicos_stats])
        tecnicos_resueltos = json.dumps([t['resueltos'] for t in tecnicos_stats])

        ultimos_tickets = tickets_base.order_by('-fecha_creacion')[:10]

        por_expirar = tickets_base.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lte=ahora + timedelta(hours=2),
            fecha_limite__gte=ahora
        ).count()

        expirados = tickets_base.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lt=ahora
        ).count()

        tickets_urgentes = tickets_base.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lte=ahora + timedelta(hours=2)
        ).order_by('fecha_limite')[:5]

        return render(request, 'dashboard.html', {
            'total': total,
            'abiertos': abiertos,
            'cerrados': cerrados,
            'total_usuarios': total_usuarios,
            'estados': estados,
            'areas_data': areas_data,
            'urgencia': urgencia,
            'sla': sla,
            'porcentaje_sla': porcentaje_sla,
            'meses_labels': json.dumps(meses_labels),
            'creados_data': json.dumps(creados_data),
            'resueltos_data': json.dumps(resueltos_data),
            'tecnicos_nombres': tecnicos_nombres,
            'tecnicos_asignados': tecnicos_asignados,
            'tecnicos_resueltos': tecnicos_resueltos,
            'ultimos_tickets': ultimos_tickets,
            'por_expirar': por_expirar,
            'expirados': expirados,
            'tickets_urgentes': tickets_urgentes,
            'ahora': ahora,
        })

    # ── ESTADÍSTICAS TÉCNICO ────────────────────────────────────────────────
    else:
        mis_tickets = Ticket.objects.filter(tecnico=request.user)
        total = mis_tickets.count()
        pendientes = mis_tickets.filter(estado__in=['nuevo', 'en_revision']).count()
        en_progreso = mis_tickets.filter(estado='en_progreso').count()
        cerrados_por_mi = mis_tickets.filter(estado='cerrado').count()

        ultimos_tickets = mis_tickets.order_by('-fecha_creacion')[:10]

        por_expirar = mis_tickets.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lte=ahora + timedelta(hours=2),
            fecha_limite__gte=ahora
        ).count()

        expirados = mis_tickets.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lt=ahora
        ).count()

        tickets_urgentes = mis_tickets.filter(
            estado__in=['nuevo', 'en_revision', 'en_progreso'],
            fecha_limite__isnull=False,
            fecha_limite__lte=ahora + timedelta(hours=2)
        ).order_by('fecha_limite')[:5]

        return render(request, 'dashboard.html', {
            'total': total,
            'pendientes': pendientes,
            'en_progreso': en_progreso,
            'cerrados_por_mi': cerrados_por_mi,
            'ultimos_tickets': ultimos_tickets,
            'por_expirar': por_expirar,
            'expirados': expirados,
            'tickets_urgentes': tickets_urgentes,
            'ahora': ahora,
        })

@login_required
def crear_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        formset = AdjuntoFormSet(request.POST, request.FILES)
        if form.is_valid():

            extensiones_permitidas = [
                '.jpg', '.jpeg', '.png', '.gif', '.webp',
                '.pdf', '.doc', '.docx'
            ]

            archivo_invalido = False
            if formset.is_valid():
                for adjunto_form in formset:
                    print("cleaned_data:", adjunto_form.cleaned_data)
                    if adjunto_form.cleaned_data.get('ruta'):
                        archivo = adjunto_form.cleaned_data['ruta']
                        print("archivo nombre:", archivo.name)
                        extension = os.path.splitext(archivo.name)[1].lower()
                        print("extension:", extension)
                        if extension not in extensiones_permitidas:
                            messages.error(request, f'Archivo "{archivo.name}" no permitido. Solo imágenes, PDF y Word.')
                            archivo_invalido = True
                            break

            if archivo_invalido:
                return render(request, 'tickets/crear.html', {'form': form, 'formset': formset})

            ticket = form.save(commit=False)
            crear_a_nombre_de = form.cleaned_data.get('crear_a_nombre_de')
            if request.user.rol == 'tecnico' and crear_a_nombre_de:
                ticket.creador = crear_a_nombre_de
            else:
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

            autoasignar = form.cleaned_data.get('autoasignar')
            prioridad_inicial = form.cleaned_data.get('prioridad_inicial')

            if request.user.rol == 'tecnico' and autoasignar and prioridad_inicial:
                ticket.tecnico = request.user
                ticket.prioridad = prioridad_inicial
                ticket.fecha_limite = calcular_fecha_limite(ticket)
                ticket.save()

                HistorialTicket.objects.create(
                    campo='prioridad',
                    valor_anterior=None,
                    valor_nuevo=prioridad_inicial,
                    ticket=ticket,
                    usuario=request.user
                )

            maestros = form.cleaned_data.get('maestros')
            if maestros:
                for maestro in maestros:
                    TicketEtiquetado.objects.create(ticket=ticket, usuario=maestro)
                    enviar_notificacion(
                        ticket=ticket,
                        destinatario_correo=maestro.correo,
                        asunto=f'Has sido etiquetado en el ticket #{ticket.id}',
                        mensaje=f'Hola {maestro.nombre},\n\nFuiste etiquetado como observador en el ticket "{ticket.titulo}".\n\nPuedes consultar los detalles desde el sistema.',
                        destinatario_usuario=maestro
                    )

            enviar_notificacion(
                ticket=ticket,
                destinatario_correo=ticket.creador.correo,
                asunto=f'Ticket #{ticket.id} creado: {ticket.titulo}',
                mensaje=f'Hola {ticket.creador.nombre},\n\nTu ticket "{ticket.titulo}" fue creado correctamente.\n\nCategoría: {ticket.categoria}\n\nPuedes hacerle seguimiento desde el sistema.',
                destinatario_usuario=ticket.creador
            )

            return redirect('lista_tickets')
    else:
        form = TicketForm()
        formset = AdjuntoFormSet()

    return render(request, 'tickets/crear.html', {'form': form, 'formset': formset})

@login_required
def agregar_adjunto(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user

    es_creador = ticket.creador == user
    es_tecnico_o_admin = user.rol in ['tecnico', 'administrador']
    esta_etiquetado = ticket.ticketetiquetado_set.filter(usuario=user).exists()

    if not (es_creador or es_tecnico_o_admin or esta_etiquetado):
        return HttpResponseForbidden('No tienes permiso para agregar adjuntos a este ticket.')

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if archivo:
            from .forms import validar_tipo_archivo
            try:
                validar_tipo_archivo(archivo)
            except Exception as e:
                messages.error(request, str(e))
                return redirect('detalle_ticket', ticket_id=ticket.id)

            adjuntos_actuales = ticket.adjuntos.count()
            if adjuntos_actuales >= 5:
                messages.error(request, 'El ticket ya tiene el máximo de 5 archivos adjuntos.')
                return redirect('detalle_ticket', ticket_id=ticket.id)

            from .models import Adjunto
            adjunto = Adjunto.objects.create(
                ticket=ticket,
                ruta=archivo,
                nombre_archivo=archivo.name,
                tipo_mime=archivo.content_type if hasattr(archivo, 'content_type') else 'desconocido'
            )
            messages.success(request, f'Archivo "{archivo.name}" adjuntado correctamente.')
        else:
            messages.error(request, 'No se seleccionó ningún archivo.')

    return redirect('detalle_ticket', ticket_id=ticket.id)


@login_required
def lista_tickets(request):
    if request.user.rol == 'administrador':
        tickets = Ticket.objects.all()
    elif request.user.rol == 'tecnico':
        areas = request.user.areas.all()
        if areas.exists():
            tickets = Ticket.objects.filter(categoria__area__in=areas)
        else:
            tickets = Ticket.objects.none()
    else:
        tickets = Ticket.objects.filter(creador=request.user)

    # Buscador
    busqueda = request.GET.get('q')
    if busqueda:
        tickets = tickets.filter(
            Q(titulo__icontains=busqueda) |
            Q(asunto__icontains=busqueda) |
            Q(creador__nombre__icontains=busqueda) |
            Q(creador__apellido__icontains=busqueda)
        )

    # Filtros comunes (técnico y admin)
    prioridad = request.GET.get('prioridad')
    if prioridad == 'sin_asignar':
        tickets = tickets.filter(prioridad__isnull=True)
    elif prioridad in ['baja', 'media', 'alta']:
        tickets = tickets.filter(prioridad=prioridad)

    estado = request.GET.get('estado')
    if estado in ['nuevo', 'en_revision', 'en_progreso', 'desestimado', 'cerrado']:
        tickets = tickets.filter(estado=estado)

    duracion = request.GET.get('duracion')
    if duracion == 'hoy':
        tickets = tickets.filter(fecha_creacion__date=timezone.now().date())
    elif duracion == 'semana':
        tickets = tickets.filter(fecha_creacion__gte=timezone.now() - timedelta(days=7))
    elif duracion == 'mes':
        tickets = tickets.filter(fecha_creacion__gte=timezone.now() - timedelta(days=30))

    orden = request.GET.get('orden')
    if orden == 'az':
        tickets = tickets.order_by('titulo')
    elif orden == 'za':
        tickets = tickets.order_by('-titulo')
    elif orden == 'reciente':
        tickets = tickets.order_by('-fecha_creacion')
    elif orden == 'antiguo':
        tickets = tickets.order_by('fecha_creacion')
    else:
        tickets = tickets.order_by('-fecha_creacion')

    # Filtros solo para administrador
    categoria = request.GET.get('categoria')
    if request.user.rol == 'administrador' and categoria:
        tickets = tickets.filter(categoria__id=categoria)

    tecnico = request.GET.get('tecnico')
    if request.user.rol == 'administrador' and tecnico:
        tickets = tickets.filter(tecnico__id=tecnico)

    from .models import Categoria, Usuario
    categorias = Categoria.objects.all()
    tecnicos = Usuario.objects.filter(rol='tecnico', is_active=True)

    return render(request, 'tickets/lista.html', {
        'tickets': tickets,
        'prioridad_actual': prioridad,
        'duracion_actual': duracion,
        'estado_actual': estado,
        'orden_actual': orden,
        'categoria_actual': categoria,
        'tecnico_actual': tecnico,
        'busqueda_actual': busqueda,
        'categorias': categorias,
        'tecnicos': tecnicos,
    })

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

    if not request.user.areas.filter(categorias=ticket.categoria).exists():
        messages.error(request, 'No puedes autoasignarte un ticket fuera de tu área.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    prioridad = request.POST.get('prioridad')
    if prioridad not in ['baja', 'media', 'alta']:
        messages.error(request, 'Debes seleccionar una prioridad al autoasignarte el ticket.')
        return redirect('detalle_ticket', ticket_id=ticket.id)

    ticket.tecnico = request.user
    ticket.prioridad = prioridad
    ticket.fecha_limite = calcular_fecha_limite(ticket)
    ticket.save()

    HistorialTicket.objects.create(
        campo='prioridad',
        valor_anterior=None,
        valor_nuevo=prioridad,
        ticket=ticket,
        usuario=request.user
    )

    enviar_notificacion(
        ticket=ticket,
        destinatario_correo=ticket.tecnico.correo,
        asunto=f'Te has autoasignado el ticket #{ticket.id}',
        mensaje=f'Hola {ticket.tecnico.nombre},\n\nTe has autoasignado el ticket "{ticket.titulo}".\n\nCategoría: {ticket.categoria}\nPrioridad: {ticket.get_prioridad_display()}',
        destinatario_usuario=ticket.tecnico
    )

    messages.success(request, 'Te has autoasignado el ticket correctamente.')
    return redirect('detalle_ticket', ticket_id=ticket.id)


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
                ticket_actualizado.fecha_limite = calcular_fecha_limite(ticket_actualizado)
                ticket_actualizado.save()
                
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
                mensaje=f'Hola {ticket_actualizado.creador.nombre},\n\nTu ticket "{ticket_actualizado.titulo}" fue actualizado.\n\nEstado: {ticket_actualizado.get_estado_display()}\nPrioridad: {ticket_actualizado.prioridad or "Sin asignar"}',
                destinatario_usuario=ticket_actualizado.creador
            )

            messages.success(request, 'Ticket actualizado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ActualizarTicketForm(instance=ticket)

    return render(request, 'tickets/actualizar.html', {'form': form, 'ticket': ticket})


@login_required
def reasignar_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Solo el administrador puede reasignar tickets.')

    tecnico_anterior = ticket.tecnico
    prioridad_anterior = ticket.prioridad

    if request.method == 'POST':
        form = ReasignarTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket_actualizado = form.save(commit=False)
            ticket_actualizado.fecha_limite = calcular_fecha_limite(ticket_actualizado)
            ticket_actualizado.save()

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
                        mensaje=f'Hola {ticket_actualizado.tecnico.nombre},\n\nEl administrador te ha asignado el ticket "{ticket_actualizado.titulo}".\n\nCategoría: {ticket_actualizado.categoria}\nPrioridad: {ticket_actualizado.prioridad or "Sin asignar"}',
                        destinatario_usuario=ticket_actualizado.tecnico
                    )

            if prioridad_anterior != ticket_actualizado.prioridad:
                HistorialTicket.objects.create(
                    campo='prioridad',
                    valor_anterior=prioridad_anterior or 'Sin asignar',
                    valor_nuevo=ticket_actualizado.prioridad or 'Sin asignar',
                    ticket=ticket_actualizado,
                    usuario=request.user
                )

            messages.success(request, 'Ticket actualizado correctamente.')
            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = ReasignarTicketForm(instance=ticket)

    return render(request, 'tickets/reasignar.html', {'form': form, 'ticket': ticket})


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
            maestros = form.cleaned_data['maestros']
            etiquetados = []
            ya_etiquetados = []

            for maestro in maestros:
                ya_etiquetado = TicketEtiquetado.objects.filter(ticket=ticket, usuario=maestro).exists()
                if ya_etiquetado:
                    ya_etiquetados.append(maestro.get_full_name())
                else:
                    TicketEtiquetado.objects.create(ticket=ticket, usuario=maestro)
                    enviar_notificacion(
                        ticket=ticket,
                        destinatario_correo=maestro.correo,
                        asunto=f'Has sido etiquetado en el ticket #{ticket.id}',
                        mensaje=f'Hola {maestro.nombre},\n\nFuiste etiquetado como observador en el ticket "{ticket.titulo}".\n\nPuedes consultar los detalles desde el sistema.',
                        destinatario_usuario=maestro
                    )
                    etiquetados.append(maestro.get_full_name())

            if etiquetados:
                messages.success(request, f'Maestros etiquetados: {", ".join(etiquetados)}.')
            if ya_etiquetados:
                messages.error(request, f'Ya estaban etiquetados: {", ".join(ya_etiquetados)}.')

            return redirect('detalle_ticket', ticket_id=ticket.id)
    else:
        form = EtiquetarMaestroForm()

    return render(request, 'tickets/etiquetar.html', {'form': form, 'ticket': ticket})


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

# ─── PANEL ADMINISTRATIVO — USUARIOS ──────────────────────────────────────────

@login_required
def admin_usuarios(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    usuarios = Usuario.objects.all().order_by('rol', 'apellido')

    busqueda = request.GET.get('q')
    if busqueda:
        usuarios = usuarios.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(correo__icontains=busqueda)
        )

    rol = request.GET.get('rol')
    if rol in ['administrador', 'tecnico', 'estudiante', 'maestro']:
        usuarios = usuarios.filter(rol=rol)

    return render(request, 'admin/usuarios.html', {
        'usuarios': usuarios,
        'busqueda_actual': busqueda,
        'rol_actual': rol,
    })


@login_required
def admin_crear_usuario(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('admin_usuarios')
    else:
        form = CrearUsuarioForm()

    return render(request, 'admin/crear_usuario.html', {'form': form})


@login_required
def admin_editar_usuario(request, usuario_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('admin_usuarios')
    else:
        form = EditarUsuarioForm(instance=usuario)

    return render(request, 'admin/editar_usuario.html', {'form': form, 'usuario': usuario})


@login_required
def admin_eliminar_usuario(request, usuario_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    usuario = get_object_or_404(Usuario, id=usuario_id)

    if usuario == request.user:
        messages.error(request, 'No puedes eliminarte a ti mismo.')
        return redirect('admin_usuarios')

    tiene_actividad = (
        Ticket.objects.filter(creador=usuario).exists() or
        Ticket.objects.filter(tecnico=usuario).exists() or
        Comentario.objects.filter(autor=usuario).exists() or
        HistorialTicket.objects.filter(usuario=usuario).exists()
    )

    if tiene_actividad:
        messages.error(request, f'No se puede eliminar a {usuario.get_full_name()} porque tiene actividad en el sistema. Desactívalo en su lugar.')
        return redirect('admin_usuarios')

    if request.method == 'POST':
        form = ConfirmarPasswordForm(request.user, request.POST)
        if form.is_valid():
            usuario.delete()
            messages.success(request, f'Usuario {usuario.get_full_name()} eliminado correctamente.')
            return redirect('admin_usuarios')
    else:
        form = ConfirmarPasswordForm(request.user)

    return render(request, 'admin/confirmar_eliminar.html', {
        'form': form,
        'objeto': usuario.get_full_name(),
        'tipo': 'usuario',
        'url_cancelar': 'admin_usuarios'
    })


@login_required
def admin_toggle_usuario(request, usuario_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    usuario = get_object_or_404(Usuario, id=usuario_id)

    if usuario == request.user:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('admin_usuarios')

    if request.method == 'POST':
        form = ConfirmarPasswordForm(request.user, request.POST)
        if form.is_valid():
            usuario.is_active = not usuario.is_active
            usuario.save()
            estado = 'activado' if usuario.is_active else 'desactivado'
            messages.success(request, f'Usuario {usuario.get_full_name()} {estado} correctamente.')
            return redirect('admin_usuarios')
    else:
        form = ConfirmarPasswordForm(request.user)

    accion = 'desactivar' if usuario.is_active else 'activar'

    return render(request, 'admin/confirmar_toggle.html', {
        'form': form,
        'usuario': usuario,
        'accion': accion,
        'url_cancelar': 'admin_usuarios'
    })
# ─── PANEL ADMINISTRATIVO — CATEGORÍAS ────────────────────────────────────────

@login_required
def admin_categorias(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    categorias = Categoria.objects.all().order_by('nombre')

    return render(request, 'admin/categorias.html', {'categorias': categorias})


@login_required
def admin_crear_categoria(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('admin_categorias')
    else:
        form = CategoriaForm()

    return render(request, 'admin/crear_categoria.html', {'form': form})


@login_required
def admin_editar_categoria(request, categoria_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    categoria = get_object_or_404(Categoria, id=categoria_id)

    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('admin_categorias')
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, 'admin/editar_categoria.html', {'form': form, 'categoria': categoria})


@login_required
def admin_eliminar_categoria(request, categoria_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    categoria = get_object_or_404(Categoria, id=categoria_id)
    tickets_asociados = Ticket.objects.filter(categoria=categoria)
    cantidad = tickets_asociados.count()

    if request.method == 'POST':
        form = EliminarCategoriaForm(request.user, categoria, request.POST)
        if form.is_valid():
            categoria_destino = form.cleaned_data.get('categoria_destino')

            if cantidad > 0:
                if not categoria_destino:
                    form.add_error('categoria_destino', 'Debes seleccionar una categoría destino porque hay tickets asociados.')
                else:
                    tickets_asociados.update(categoria=categoria_destino)
                    categoria.delete()
                    messages.success(request, f'Categoría eliminada. {cantidad} ticket(s) movidos a "{categoria_destino.nombre}".')
                    return redirect('admin_categorias')
            else:
                categoria.delete()
                messages.success(request, f'Categoría "{categoria.nombre}" eliminada correctamente.')
                return redirect('admin_categorias')
    else:
        form = EliminarCategoriaForm(request.user, categoria)

    return render(request, 'admin/eliminar_categoria.html', {
        'form': form,
        'categoria': categoria,
        'cantidad': cantidad,
    })

# ─── PANEL ADMINISTRATIVO — ÁREAS ─────────────────────────────────────────────

@login_required
def admin_areas(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    areas = Area.objects.all().order_by('nombre')
    return render(request, 'admin/areas.html', {'areas': areas})


@login_required
def admin_crear_area(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    if request.method == 'POST':
        form = AreaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Área creada correctamente.')
            return redirect('admin_areas')
    else:
        form = AreaForm()

    return render(request, 'admin/crear_area.html', {'form': form})


@login_required
def admin_editar_area(request, area_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    area = get_object_or_404(Area, id=area_id)

    if request.method == 'POST':
        form = AreaForm(request.POST, instance=area)
        if form.is_valid():
            form.save()
            messages.success(request, 'Área actualizada correctamente.')
            return redirect('admin_areas')
    else:
        form = AreaForm(instance=area)

    return render(request, 'admin/editar_area.html', {'form': form, 'area': area})


@login_required
def admin_eliminar_area(request, area_id):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('Acceso denegado.')

    area = get_object_or_404(Area, id=area_id)
    categorias_asociadas = Categoria.objects.filter(area=area).count()

    if request.method == 'POST':
        form = ConfirmarPasswordForm(request.user, request.POST)
        if form.is_valid():
            if categorias_asociadas > 0:
                messages.error(request, f'No se puede eliminar el área "{area.nombre}" porque tiene {categorias_asociadas} categoría(s) asociada(s).')
                return redirect('admin_areas')
            area.delete()
            messages.success(request, f'Área "{area.nombre}" eliminada correctamente.')
            return redirect('admin_areas')
    else:
        form = ConfirmarPasswordForm(request.user)

    return render(request, 'admin/confirmar_eliminar.html', {
        'form': form,
        'objeto': area.nombre,
        'tipo': 'área',
        'url_cancelar': 'admin_areas',
        'advertencia': f'Esta área tiene {categorias_asociadas} categoría(s) asociada(s). No podrá eliminarse.' if categorias_asociadas > 0 else None
    })