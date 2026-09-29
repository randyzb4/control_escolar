from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def coordinador_requerido(view_func):
    """
    Permite el acceso solo a usuarios autenticados con rol 'coordinador'.
    Si no está autenticado, redirige a login.
    Si está autenticado pero no es coordinador, muestra mensaje y redirige al dashboard.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('horarios:login')
        try:
            perfil = request.user.perfil
        except Exception:
            messages.error(request, 'No tienes perfil asignado. Contacta al administrador.')
            return redirect('horarios:dashboard')
        if perfil.rol != 'coordinador':
            messages.error(request, 'No tienes permisos para realizar esta acción.')
            return redirect('horarios:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
