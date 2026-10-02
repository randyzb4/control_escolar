from django import template
from horarios.permisos import tiene_permiso

register = template.Library()


@register.simple_tag
def puede_ver(user, modulo):
    return tiene_permiso(user, modulo, 'ver')


@register.simple_tag
def puede_editar(user, modulo):
    return tiene_permiso(user, modulo, 'editar')