from django import forms
from .models import Ticket, Usuario, Adjunto, Comentario
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError


# Formularios para la creación de tickets, etiquetado de maestros y adjuntado de archivos

class TicketForm(forms.ModelForm):
    maestros = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol='maestro', activo=True),
        required=False,
        label='Etiquetar maestros (opcional)',
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']


class EtiquetarMaestroForm(forms.Form):
    maestros = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol='maestro', activo=True),
        required=False,
        label='Etiquetar maestros',
        widget=forms.CheckboxSelectMultiple
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
        fields = ['tecnico']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tecnico'].queryset = Usuario.objects.filter(rol='tecnico', activo=True)

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
            'contenido': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Escribe un comentario...'}),
        }

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
    
class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')
