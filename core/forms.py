from django import forms
from .models import Ticket, Usuario, Adjunto
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.forms import inlineformset_factory


# Formulario para la creación de tickets
class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']


AdjuntoFormSet = inlineformset_factory(
    Ticket,
    Adjunto,
    fields=['ruta'],
    extra=5,
    max_num=5,
    can_delete=False
)


class ActualizarTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['estado', 'prioridad']

class ReasignarTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['tecnico']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tecnico'].queryset = Usuario.objects.filter(rol='tecnico', activo=True)

class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')
