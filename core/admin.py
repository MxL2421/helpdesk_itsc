from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Categoria, Ticket, Area


class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('correo', 'nombre', 'apellido', 'rol', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_active')
    search_fields = ('nombre', 'apellido', 'correo', 'matricula')
    ordering = ('correo',)

    fieldsets = (
        (None, {'fields': ('correo', 'password')}),
        ('Información personal', {'fields': ('nombre', 'apellido', 'matricula', 'carrera', 'rol')}),
        ('Áreas asignadas', {'fields': ('areas',)}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'fields': ('correo', 'nombre', 'apellido', 'rol', 'password1', 'password2'),
        }),
    )


class TicketAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'estado', 'prioridad', 'creador', 'tecnico', 'categoria')
    list_filter = ('estado', 'prioridad', 'categoria')
    search_fields = ('titulo',)

admin.site.register(Ticket, TicketAdmin)

class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Categoria, CategoriaAdmin)

admin.site.site_header = 'Help Desk ITSC'
admin.site.site_title = 'Help Desk ITSC'
admin.site.index_title = 'Panel de Administración'