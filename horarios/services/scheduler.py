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
    return Asignacion.objects.filter(
        grupo_materia__grupo=grupo_materia.grupo,
        slot=slot,
    ).exists()

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

            if profesor_disponible(gm.profesor, slot) and grupo_ocupado(gm, slot):
                aula = buscar_aula_para(gm.materia, slot)
                if aula:
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
                        # Si hay conflicto, saltamos este slot
                        continue

    return asignadas
