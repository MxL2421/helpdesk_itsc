from django import forms
from .models import Ticket, Usuario, Adjunto, Comentario
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.forms import inlineformset_factory


# Formularios para la creación de tickets, etiquetado de maestros y adjuntado de archivos

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']

class EtiquetarMaestroForm(forms.Form):
    maestro = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='maestro', activo=True),
        label='Maestro a etiquetar'
    )

AdjuntoFormSet = inlineformset_factory(
    Ticket,
    Adjunto,
    fields=['ruta'],
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

class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')
