from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **extra_fields):
        if not correo:
            raise ValueError('El correo es obligatorio')
        correo = self.normalize_email(correo)
        user = self.model(correo=correo, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, password=None, **extra_fields):
        extra_fields.setdefault('rol', 'administrador')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(correo, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    ROL_CHOICES = [
        ('administrador', 'Administrador'),
        ('tecnico', 'Técnico'),
        ('estudiante', 'Estudiante'),
        ('maestro', 'Maestro'),
    ]

    DOMINIOS_ROL = {
        'administrador': '@adm.itsc.edu.do',
        'tecnico': '@tec.itsc.edu.do',
        'estudiante': '@est.itsc.edu.do',
        'maestro': '@doc.itsc.edu.do',
    }
    
    areas = models.ManyToManyField(
    'Categoria',
    blank=True,
    related_name='tecnicos',
    verbose_name='Áreas asignadas'
    )

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    matricula = models.CharField(max_length=20, unique=True, null=True, blank=True)
    correo = models.EmailField(max_length=150, unique=True)
    carrera = models.CharField(max_length=150, null=True, blank=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    activo = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido', 'rol']

    objects = UsuarioManager()

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.rol})'

    def get_full_name(self):
        return f'{self.nombre} {self.apellido}'


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class Ticket(models.Model):
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('en_revision', 'En revisión'),
        ('en_progreso', 'En progreso'),
        ('desestimado', 'Desestimado'),
        ('cerrado', 'Cerrado'),
    ]

    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ]

    titulo = models.CharField(max_length=200)
    asunto = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='nuevo')
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_limite = models.DateTimeField(null=True, blank=True)
    creador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='tickets_creados', db_column='creador_id')
    tecnico = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_asignados', db_column='tecnico_id')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column='categoria_id')

    class Meta:
        db_table = 'ticket'

    def __str__(self):
        return f'{self.titulo} [{self.estado}]'


class Adjunto(models.Model):
    nombre_archivo = models.CharField(max_length=255)
    ruta = models.FileField(upload_to='adjuntos/')
    tipo_mime = models.CharField(max_length=100)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='adjuntos', db_column='ticket_id')

    class Meta:
        db_table = 'adjunto'

    def __str__(self):
        return self.nombre_archivo


class TicketEtiquetado(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, db_column='ticket_id')
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='usuario_id')

    class Meta:
        db_table = 'ticket_etiquetado'
        unique_together = ('ticket', 'usuario')

    def __str__(self):
        return f'{self.usuario} etiquetado en ticket {self.ticket.id}'


class Comentario(models.Model):
    contenido = models.TextField()
    es_privado = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comentarios', db_column='ticket_id')
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='autor_id')

    class Meta:
        db_table = 'comentario'

    def __str__(self):
        return f'Comentario de {self.autor} en ticket {self.ticket.id}'


class HistorialTicket(models.Model):
    campo = models.CharField(max_length=100)
    valor_anterior = models.CharField(max_length=255, null=True, blank=True)
    valor_nuevo = models.CharField(max_length=255, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='historial', db_column='ticket_id')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='usuario_id')

    class Meta:
        db_table = 'historial_ticket'

    def __str__(self):
        return f'{self.campo} cambiado en ticket {self.ticket.id}'


class Notificacion(models.Model):
    asunto = models.CharField(max_length=200)
    mensaje = models.TextField()
    correo_destino = models.EmailField(max_length=150)
    enviada = models.BooleanField(default=False)
    leida = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='notificaciones', db_column='ticket_id')
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones_recibidas')

    class Meta:
        db_table = 'notificacion'

    def __str__(self):
        return f'Notificacion a {self.correo_destino} — {self.asunto}'