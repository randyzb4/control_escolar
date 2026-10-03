"""
Sistema de permisos granulares por módulo.

Uso:
    from horarios.permisos import tiene_permiso, requiere_permiso

    # En una vista
    @login_required
    @requiere_permiso('grupos', 'ver')
    def lista_grupos(request):
        ...

    # En un template (necesita un templatetag que llame a tiene_permiso)
    if tiene_permiso(request.user, 'grupos', 'editar'):
        ...
"""
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


MODULOS_DISPONIBLES = [
    ('dashboard', 'Dashboard'),
    ('grupos', 'Grupos'),
    ('subgrupos', 'Gestión de Subgrupos'),
    ('lista_asistencia', 'Lista de Asistencia Imprimible'),
    ('asistencias_grupo', 'Asistencias del Grupo'),
    ('profesores', 'Profesores'),
    ('carga', 'Carga Docente'),
    ('resumen', 'Resumen'),
    ('asignaciones', 'Asignaciones'),
    ('configurar', 'Configurar Horario'),
    ('incidencias', 'Incidencias'),
    ('desempeno', 'Desempeño'),
    ('planeaciones', 'Planeaciones'),
    ('calendario', 'Calendario'),
    ('reportes', 'Reportes'),
    ('configuracion', 'Configuración Institucional'),
    ('admin_django', 'Admin Django'),
]

ACCIONES_DISPONIBLES = [
    ('ver', 'Ver'),
    ('editar', 'Editar'),
]


def tiene_permiso(user, modulo, accion='ver'):
    """
    Devuelve True si el usuario tiene permiso para el módulo y acción dados.

    Reglas:
    - Sin autenticar: False.
    - Staff / superuser: True (acceso total).
    - Coordinador: True (compatibilidad con sistema actual).
    - Profesor: True para sus módulos internos (dashboard, mi_horario, etc.).
    - Auxiliar / otros: revisa modulos_permitidos.
    """
    if not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    if not hasattr(user, 'perfil'):
        return False

    # Coordinador: acceso total
    if user.perfil.rol == 'coordinador':
        return True

    # Profesor: solo módulos internos de profesor
    if user.perfil.rol == 'profesor':
         modulos_profesor = {
            'dashboard',
            'mi_horario',
            'mis_grupos',
            'capturar',
            'pase_lista',
            'bitacora',
            # Módulos compartidos con coordinador (las vistas filtran
            # los datos por profesor automáticamente)
            'incidencias',
            'desempeno',
            'planeaciones',
            'calendario',
        }
         return modulo in modulos_profesor

    # Auxiliar, consulta, etc.: revisar modulos_permitidos
    modulos = user.perfil.modulos_permitidos or {}
    return modulos.get(modulo, {}).get(accion, False)


def requiere_permiso(modulo, accion='ver'):
    """
    Decorador para vistas que requieren permiso.
    Si el usuario no tiene permiso, redirige al dashboard con un mensaje.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not tiene_permiso(request.user, modulo, accion):
                messages.error(
                    request,
                    'No tienes permiso para acceder a este módulo.'
                )
                return redirect('horarios:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator