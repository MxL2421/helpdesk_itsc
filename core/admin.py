from django.contrib import admin
from .models import Usuario, Categoria


class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'correo', 'rol', 'activo')
    list_filter = ('rol', 'activo')
    search_fields = ('nombre', 'apellido', 'correo', 'matricula')


class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Categoria, CategoriaAdmin)

admin.site.site_header = 'Help Desk ITSC'
admin.site.site_title = 'Help Desk ITSC'
admin.site.index_title = 'Panel de Administración'