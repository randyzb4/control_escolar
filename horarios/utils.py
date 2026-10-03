from django.db.models import Q
from .models import Alumno, AlumnoSubgrupoMateria


def alumnos_para_grupo_materia(gm):
    """
    Devuelve los alumnos que deben aparecer en un GrupoMateria,
    respetando subgrupos y excepciones por materia.

    Reglas:
    - Si gm.subgrupo == '': todos los alumnos del grupo.
    - Si gm.subgrupo != '':
      * Alumnos con subgrupo global == gm.subgrupo, MENOS los que
        tengan una excepción para esta materia con subgrupo distinto.
      * MÁS alumnos con excepción para esta materia == gm.subgrupo.
    """
    alumnos = Alumno.objects.filter(grupo=gm.grupo, activo=True)

    if not gm.subgrupo:
        return alumnos

    # Excepciones para esta materia
    excepciones = AlumnoSubgrupoMateria.objects.filter(
        materia=gm.materia
    ).values_list('alumno_id', 'subgrupo')

    # Alumnos con excepción que apunta a otro subgrupo (excluir del global)
    excluidos = [
        alumno_id
        for alumno_id, sub in excepciones
        if sub != gm.subgrupo
    ]

    # Alumnos con excepción que apunta a este subgrupo (incluir extra)
    incluidos_por_excepcion = [
        alumno_id
        for alumno_id, sub in excepciones
        if sub == gm.subgrupo
    ]

    # Alumnos con subgrupo global == gm.subgrupo, menos excluidos
    alumnos_globales = alumnos.filter(subgrupo=gm.subgrupo).exclude(id__in=excluidos)

    # Alumnos con excepción == gm.subgrupo (aunque su global sea distinto)
    alumnos_excepcion = alumnos.filter(id__in=incluidos_por_excepcion)

    # Unir ambos querysets
    return (alumnos_globales | alumnos_excepcion).distinct().order_by(
        'apellido_paterno', 'apellido_materno', 'nombre'
    )
