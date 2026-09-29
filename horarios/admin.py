from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.core.exceptions import ValidationError
from .models import Asistencia
from .models import Incidencia
from .models import EvidenciaDesempeno, CalificacionEvidencia
from .models import Planeacion, SesionPlaneacion
from .models import EventoCalendario

from .models import (
    Profesor, Aula, Materia, Grupo, GrupoMateria,
    DisponibilidadProfesor, SlotHorario, Asignacion,
    PerfilUsuario, ConfiguracionHorario,
    Alumno, Periodo, Calificacion,
)


# ============================================================
#  Modelos base
# ============================================================

@admin.register(Profesor)
class ProfesorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'tiene_usuario')
    search_fields = ('nombre',)
    list_filter = ('activo',)
    actions = ['crear_usuarios']

    def tiene_usuario(self, obj):
        from .models import PerfilUsuario
        tiene = PerfilUsuario.objects.filter(profesor=obj, rol='profesor').exists()
        if tiene:
            return '✅ Sí'
        return '❌ No'
    tiene_usuario.short_description = 'Usuario'

    @admin.action(description='Crear usuario para profesores seleccionados')
    def crear_usuarios(self, request, queryset):
        from django.contrib.auth.models import User
        from .models import PerfilUsuario
        import unicodedata

        creados = 0
        for profesor in queryset:
            if PerfilUsuario.objects.filter(profesor=profesor, rol='profesor').exists():
                continue

            # Generar username desde el nombre
            base = profesor.nombre.lower().replace(' ', '.')
            base = ''.join(c for c in unicodedata.normalize('NFD', base)
                          if unicodedata.category(c) != 'Mn')
            username = base
            contador = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{contador}"
                contador += 1

            user = User.objects.create_user(
                username=username,
                password='cambiar123',
                email=profesor.email or ''
            )
            PerfilUsuario.objects.create(
                usuario=user,
                rol='profesor',
                profesor=profesor
            )
            creados += 1

        self.message_user(request, f'{creados} usuarios creados. Contraseña temporal: cambiar123')



@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'capacidad', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('nombre',)


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'horas_semanales', 'requiere_laboratorio')
    list_filter = ('requiere_laboratorio',)
    search_fields = ('nombre',)


class GrupoMateriaInline(admin.TabularInline):
    model = GrupoMateria
    extra = 1


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    inlines = [GrupoMateriaInline]


@admin.register(GrupoMateria)
class GrupoMateriaAdmin(admin.ModelAdmin):
    list_display = ('grupo', 'materia', 'profesor', 'horas_semanales')
    list_filter = ('grupo', 'materia', 'profesor')
    search_fields = ('grupo__nombre', 'materia__nombre', 'profesor__nombre')


@admin.register(DisponibilidadProfesor)
class DisponibilidadProfesorAdmin(admin.ModelAdmin):
    list_display = ('profesor', 'dia', 'hora_inicio', 'hora_fin')
    list_filter = ('dia', 'profesor')


@admin.register(SlotHorario)
class SlotHorarioAdmin(admin.ModelAdmin):
    list_display = ('dia', 'hora_inicio', 'hora_fin')
    list_filter = ('dia',)
    ordering = ('dia', 'hora_inicio')


# ============================================================
#  Asignación con validación
# ============================================================

class AsignacionForm(forms.ModelForm):
    class Meta:
        model = Asignacion
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()

        instance = self.instance
        for campo, valor in cleaned_data.items():
            setattr(instance, campo, valor)

        try:
            instance.full_clean(exclude=None)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)

        return cleaned_data


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    form = AsignacionForm
    list_display = ('grupo_materia', 'profesor', 'aula', 'slot', 'generado_automaticamente')
    list_filter = ('slot__dia', 'profesor', 'aula', 'generado_automaticamente')
    search_fields = ('grupo_materia__grupo__nombre', 'profesor__nombre')


# ============================================================
#  Perfil de usuario (roles)
# ============================================================

class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil'
    fk_name = 'usuario'


class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'profesor')
    list_filter = ('rol',)
    search_fields = ('usuario__username', 'profesor__nombre')
    autocomplete_fields = ('profesor',)


# ============================================================
#  Configuración de horario base
# ============================================================

@admin.register(ConfiguracionHorario)
class ConfiguracionHorarioAdmin(admin.ModelAdmin):
    list_display = ('hora_inicio', 'hora_fin', 'duracion_bloque', 'dias_activos', 'actualizado_en')
    fieldsets = (
        ('Jornada', {
            'fields': ('hora_inicio', 'hora_fin', 'duracion_bloque', 'dias_activos')
        }),
        ('Recesos (opcionales)', {
            'fields': ('receso1_inicio', 'receso1_fin', 'receso2_inicio', 'receso2_fin'),
            'description': 'Si defines un receso, los slots se generarán evitando ese rango horario.'
        }),
    )
    actions = ['regenerar_slots']

    def regenerar_slots(self, request, queryset):
        for config in queryset:
            total = config.generar_slots()
            self.message_user(request, f'{total} slots generados.')
    regenerar_slots.short_description = 'Regenerar slots automáticamente'


# ============================================================
#  Alumnos, Periodos y Calificaciones
# ============================================================

@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'nombre_completo', 'grupo', 'activo')
    list_filter = ('activo', 'grupo')
    search_fields = ('matricula', 'nombre', 'apellido_paterno', 'apellido_materno')
    list_editable = ('activo',)


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'fecha_inicio', 'fecha_fin', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre',)
    date_hierarchy = 'fecha_inicio'


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'grupo_materia', 'periodo', 'calificacion', 'capturada_por')
    list_filter = ('periodo', 'grupo_materia__materia', 'grupo_materia__grupo')
    search_fields = ('alumno__nombre', 'alumno__apellido_paterno', 'alumno__matricula')
    autocomplete_fields = ('alumno',)

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'grupo_materia', 'fecha', 'estado', 'registrada_por')
    list_filter = ('estado', 'fecha', 'grupo_materia__grupo', 'grupo_materia__materia')
    search_fields = ('alumno__nombre', 'alumno__apellido_paterno', 'alumno__matricula')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('alumno',)


@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'alumno', 'grupo_materia', 'tipo_reporte', 'reportado_por')
    list_filter = ('tipo_reporte', 'fecha', 'grupo_materia__grupo', 'grupo_materia__materia')
    search_fields = ('alumno__nombre', 'alumno__apellido_paterno', 'alumno__matricula', 'resumen')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('alumno',)



class CalificacionEvidenciaInline(admin.TabularInline):
    model = CalificacionEvidencia
    extra = 1
    autocomplete_fields = ('alumno',)


@admin.register(EvidenciaDesempeno)
class EvidenciaDesempenoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'grupo_materia', 'periodo', 'tipo', 'porcentaje', 'fecha')
    list_filter = ('tipo', 'periodo', 'grupo_materia__grupo', 'grupo_materia__materia')
    search_fields = ('nombre', 'grupo_materia__grupo__nombre', 'grupo_materia__materia__nombre')
    date_hierarchy = 'fecha'
    inlines = [CalificacionEvidenciaInline]


@admin.register(CalificacionEvidencia)
class CalificacionEvidenciaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'evidencia', 'calificacion', 'capturada_por')
    list_filter = ('evidencia__periodo', 'evidencia__grupo_materia__grupo')
    search_fields = ('alumno__nombre', 'alumno__apellido_paterno', 'alumno__matricula')
    autocomplete_fields = ('alumno',)




class SesionPlaneacionInline(admin.TabularInline):
    model = SesionPlaneacion
    extra = 1
    fields = ('numero', 'fecha', 'duracion_minutos', 'recursos', 'producto', 'actividades')
    ordering = ('numero',)


@admin.register(Planeacion)
class PlaneacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'profesor', 'grupo_materia', 'periodo',
                    'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'periodo', 'grupo_materia__grupo',
                   'grupo_materia__materia', 'profesor')
    search_fields = ('titulo', 'tema', 'objetivo',
                     'grupo_materia__grupo__nombre',
                     'grupo_materia__materia__nombre',
                     'profesor__nombre')
    date_hierarchy = 'fecha_inicio'
    inlines = [SesionPlaneacionInline]


@admin.register(SesionPlaneacion)
class SesionPlaneacionAdmin(admin.ModelAdmin):
    list_display = ('planeacion', 'numero', 'fecha', 'duracion_minutos')
    list_filter = ('planeacion', 'fecha')
    search_fields = ('planeacion__titulo', 'producto', 'recursos')



@admin.register(EventoCalendario)
class EventoCalendarioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'titulo', 'tipo', 'todo_el_dia', 'creado_por')
    list_filter = ('tipo', 'todo_el_dia', 'fecha')
    search_fields = ('titulo', 'descripcion')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)


from .models import ConfiguracionInstitucion

@admin.register(ConfiguracionInstitucion)
class ConfiguracionInstitucionAdmin(admin.ModelAdmin):
    list_display = ('nombre_institucion', 'ciclo_escolar', 'actualizado_en')
    fieldsets = (
        ('Identidad', {
            'fields': ('nombre_institucion', 'logo', 'lema')
        }),
        ('Contacto', {
            'fields': ('direccion', 'telefono', 'email', 'sitio_web')
        }),
        ('Información escolar', {
            'fields': ('ciclo_escolar', 'director')
        }),
    )

    def has_add_permission(self, request):
        if ConfiguracionInstitucion.objects.exists():
            return False
        return super().has_add_permission(request)
