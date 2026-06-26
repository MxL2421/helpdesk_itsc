from django import forms
from .models import Ticket, Usuario
from django.contrib.auth.forms import AuthenticationForm
from django import forms



class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')


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