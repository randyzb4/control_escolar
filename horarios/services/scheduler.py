from ..models import (
    GrupoMateria, SlotHorario, Asignacion,
    DisponibilidadProfesor, Aula,
)

def profesor_disponible(profesor, slot):
    if not profesor:
        return True
    tiene_disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor).exists()
    if not tiene_disponibilidad:
        return True
    return DisponibilidadProfesor.objects.filter(
        profesor=profesor,
        dia=slot.dia,
        hora_inicio__lte=slot.hora_inicio,
        hora_fin__gte=slot.hora_fin,
    ).exists()

def profesor_ocupado(profesor, slot):
    if not profesor:
        return False
    return Asignacion.objects.filter(profesor=profesor, slot=slot).exists()

def grupo_ocupado(grupo_materia, slot):
    """
    Devuelve True si el grupo ya tiene una clase asignada en ese slot
    que CHOCA con la del grupo_materia dado.

    Reglas:
    - Si grupo_materia.subgrupo == '' (todo el grupo): choca con cualquier otra
      asignación del mismo grupo en el mismo slot.
    - Si grupo_materia.subgrupo != '': choca solo si la otra asignación
      es del mismo grupo Y (tiene subgrupo vacío O el mismo subgrupo).
    """
    otras = Asignacion.objects.filter(
        grupo_materia__grupo=grupo_materia.grupo,
        slot=slot,
    )

    for otra in otras:
        gm_otra = otra.grupo_materia

        if not grupo_materia.subgrupo or not gm_otra.subgrupo:
            return True
        if grupo_materia.subgrupo == gm_otra.subgrupo:
            return True

    return False

def buscar_aula_para(materia, slot):
    aulas_ocupadas = Asignacion.objects.filter(slot=slot, aula__isnull=False).values_list('aula_id', flat=True)
    qs = Aula.objects.exclude(id__in=aulas_ocupadas)
    if materia.requiere_laboratorio:
        qs = qs.filter(tipo='laboratorio')
    return qs.first()

def generar_horario():
    Asignacion.objects.all().delete()
    slots = list(SlotHorario.objects.all().order_by('dia', 'hora_inicio'))
    grupo_materias = list(GrupoMateria.objects.all().order_by('grupo__nombre', 'materia__nombre'))
    asignadas = 0

    for gm in grupo_materias:
        horas_pendientes = gm.materia.horas_semanales

        for slot in slots:
            if horas_pendientes <= 0:
                break

            # 1. Profesor disponible según su disponibilidad declarada
            if not profesor_disponible(gm.profesor, slot):
                continue

            # 2. Profesor no ocupado en otro grupo
            if profesor_ocupado(gm.profesor, slot):
                continue

            # 3. Grupo no ocupado (considerando subgrupos)
            if grupo_ocupado(gm, slot):
                continue

            # 4. Buscar aula libre
            aula = buscar_aula_para(gm.materia, slot)
            if not aula:
                continue

            # 5. Crear la asignación
            try:
                asignacion = Asignacion(
                    grupo_materia=gm,
                    profesor=gm.profesor,
                    aula=aula,
                    slot=slot,
                    generado_automaticamente=True,
                )
                asignacion.full_clean()
                asignacion.save()
                horas_pendientes -= 1
                asignadas += 1
            except Exception:
                continue

    no_asignadas = []
    for gm in grupo_materias:
        horas_asignadas = Asignacion.objects.filter(grupo_materia=gm).count()
        if horas_asignadas < gm.materia.horas_semanales:
            faltantes = gm.materia.horas_semanales - horas_asignadas
            no_asignadas.append({
                'grupo': gm.grupo.nombre,
                'materia': gm.materia.nombre,
                'profesor': gm.profesor.nombre if gm.profesor else 'Sin profesor',
                'faltantes': faltantes,
            })

    return asignadas, no_asignadas
