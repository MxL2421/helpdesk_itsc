from django import forms
from .models import Ticket
from django.contrib.auth.forms import AuthenticationForm
from django import forms



class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['titulo', 'asunto', 'categoria']


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')