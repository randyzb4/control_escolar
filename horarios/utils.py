from django.db.models import Q
from .models import Alumno, AlumnoSubgrupoMateria, Asignacion
from datetime import timedelta


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


def _siguiente_dia_habil(fecha):
    """
    Si la fecha es sábado o domingo, devuelve el lunes siguiente.
    Si es día hábil, devuelve la misma fecha.
    """
    while fecha.isoweekday() > 5:  # 6=Sábado, 7=Domingo
        fecha += timedelta(days=1)
    return fecha


def calcular_fecha_limite(evidencia, gm):
    """
    Calcula la fecha límite para entregar una evidencia.

    Reglas:
    - Si la materia es diaria (es_diaria=True): fecha_evidencia + 1 día
      (ajustado al siguiente día hábil si cae en fin de semana).
    - Si la materia NO es diaria (es_diaria=False): próxima clase
      de esa materia en ese grupo después de la fecha de la evidencia.

    Devuelve un objeto date con la fecha límite.
    """
    if gm.materia.es_diaria:
        fecha_limite = evidencia.fecha + timedelta(days=1)
        return _siguiente_dia_habil(fecha_limite)

    # Materia no diaria: buscar los días de clase de esa materia en el grupo
    dias_clase = Asignacion.objects.filter(
        grupo_materia=gm
    ).values_list('slot__dia', flat=True).distinct().order_by('slot__dia')

    dias_lista = sorted(set(dias_clase))

    if not dias_lista:
        # Sin horario: fallback +2 días, ajustado a día hábil
        fecha_limite = evidencia.fecha + timedelta(days=2)
        return _siguiente_dia_habil(fecha_limite)

    dia_evidencia = evidencia.fecha.isoweekday()  # 1=Lun, 7=Dom

    # Buscar el próximo día de clase después de la fecha de la evidencia
    for d in dias_lista:
        if d > dia_evidencia:
            return evidencia.fecha + timedelta(days=(d - dia_evidencia))

    # No hay día después en la misma semana: ir a la siguiente
    primer_dia = dias_lista[0]
    return evidencia.fecha + timedelta(days=(7 - dia_evidencia + primer_dia))