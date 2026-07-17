from django import forms
from .models import Ticket, Usuario, Adjunto, Comentario, Categoria, Area
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm


# Formularios para la creación de tickets, etiquetado de maestros y adjuntado de archivos

class TicketForm(forms.ModelForm):
    maestros = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol='maestro', is_active=True),
        required=False,
        label='Etiquetar maestros (opcional)',
        widget=forms.SelectMultiple(attrs={'style': 'width: 100%'})
    )

    # Campos adicionales para técnicos
    crear_a_nombre_de = forms.ModelChoiceField(
        queryset=Usuario.objects.all(),
        required=False,
        label='Crear a nombre de (opcional)',
        empty_label='Selecciona un usuario'
    )

    autoasignar = forms.BooleanField(
        required=False,
        label='Asignarme este ticket'
    )

    prioridad_inicial = forms.ChoiceField(
        choices=[('', 'Selecciona prioridad'), ('baja', 'Baja'), ('media', 'Media'), ('alta', 'Alta')],
        required=False,
        label='Prioridad'
    )

    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']
        labels = {
            'titulo': 'Título',
            'asunto': 'Descripción del problema',
            'categoria': 'Categoría',
        }
        widgets = {
            'titulo': forms.TextInput(attrs={
                'placeholder': 'Escribe un título breve y descriptivo',
                'class': 'w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500',
            }),
            'asunto': forms.Textarea(attrs={
                'placeholder': 'Describe el problema con el mayor detalle posible',
                'rows': 4,
                'class': 'w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500',
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500',
            }),
        }


class EtiquetarMaestroForm(forms.Form):
    maestros = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol='maestro', is_active=True),
        required=False,
        label='Etiquetar maestros',
        widget=forms.SelectMultiple(attrs={'style': 'width: 100%'})
    )

def validar_tipo_archivo(archivo):
    tipos_permitidos = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    if hasattr(archivo, 'content_type') and archivo.content_type not in tipos_permitidos:
        raise ValidationError(
            'Tipo de archivo no permitido. Solo se aceptan imágenes, PDF y documentos Word.'
        )
    
class AdjuntoForm(forms.ModelForm):
    class Meta:
        model = Adjunto
        fields = ['ruta']

    def clean_ruta(self):
        archivo = self.cleaned_data.get('ruta')
        if archivo:
            validar_tipo_archivo(archivo)
        return archivo


AdjuntoFormSet = inlineformset_factory(
    Ticket,
    Adjunto,
    form=AdjuntoForm,
    extra=5,
    max_num=5,
    can_delete=False
)

# Actualización de tickets

class ActualizarTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['estado', 'prioridad']

# Reasignación de ticket

class ReasignarTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['tecnico', 'prioridad']
        labels = {
            'tecnico': 'Técnico',
            'prioridad': 'Prioridad',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tecnico'].queryset = Usuario.objects.filter(rol='tecnico', is_active=True)
        self.fields['prioridad'].required = False

# Redirección de ticket (cambio de categoría)

class RedirigirTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['categoria']

# Comentarios privados/públicos

class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ['contenido', 'es_privado']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Escribe un comentario...',
                'class': 'w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-red-500',
            }),
        }

    
class CambiarContrasenaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Contraseña actual'
        self.fields['new_password1'].label = 'Nueva contraseña'
        self.fields['new_password2'].label = 'Confirmar nueva contraseña'
    
class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')


# Panel administrativo

class CrearUsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput()
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput()
    )

    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'correo', 'rol', 'matricula', 'carrera', 'areas']
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'correo': 'Correo institucional',
            'rol': 'Rol',
            'matricula': 'Matrícula',
            'carrera': 'Carrera',
            'areas': 'Áreas asignadas',
        }
        widgets = {
            'areas': forms.CheckboxSelectMultiple,
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2

    def clean_correo(self):
        correo = self.cleaned_data.get('correo')
        rol = self.cleaned_data.get('rol')
        dominios = {
            'administrador': '@adm.itsc.edu.do',
            'tecnico': '@tec.itsc.edu.do',
            'estudiante': '@est.itsc.edu.do',
            'maestro': '@doc.itsc.edu.do',
        }
        if rol and correo:
            dominio_esperado = dominios.get(rol)
            if dominio_esperado and not correo.endswith(dominio_esperado):
                raise forms.ValidationError(f'El correo debe terminar en {dominio_esperado}')
        return correo

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.save_m2m()
        return user


class EditarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'correo', 'rol', 'matricula', 'carrera', 'areas', 'is_active']
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'correo': 'Correo institucional',
            'rol': 'Rol',
            'matricula': 'Matrícula',
            'carrera': 'Carrera',
            'areas': 'Áreas asignadas',
            'is_active': 'Usuario activo',
        }
        widgets = {
            'areas': forms.CheckboxSelectMultiple,
        }


class ConfirmarPasswordForm(forms.Form):
    password = forms.CharField(
        label='Confirma tu contraseña para continuar',
        widget=forms.PasswordInput()
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise forms.ValidationError('Contraseña incorrecta.')
        return password
    
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'area']
        labels = {
            'nombre': 'Nombre de la categoría',
            'area': 'Área',
        }

class EliminarCategoriaForm(forms.Form):
    categoria_destino = forms.ModelChoiceField(
        queryset=Categoria.objects.none(),
        label='Mover tickets a categoría',
        required=False,
        empty_label='Selecciona una categoría destino'
    )
    password = forms.CharField(
        label='Confirma tu contraseña',
        widget=forms.PasswordInput()
    )

    def __init__(self, user, categoria_actual, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['categoria_destino'].queryset = Categoria.objects.exclude(id=categoria_actual.id)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise forms.ValidationError('Contraseña incorrecta.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
    
class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['nombre']
        labels = {
            'nombre': 'Nombre del área',
        }