# verificar_calculo.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import Periodo, Alumno, Calificacion, Materia

# Ajusta estos valores con datos reales
alumno = Alumno.objects.first()
print(f"Alumno: {alumno.nombre_completo()} (id={alumno.id})")
print(f"Grupo: {alumno.grupo.nombre}")
print()

t1 = Periodo.objects.get(nombre='Trimestre 1')
periodos_t1 = t1.hijos.filter(tipo='periodo')
print(f"Periodos del Trimestre 1: {[p.nombre for p in periodos_t1]}")
print()

# Materias del grupo
materias = Materia.objects.filter(grupomateria__grupo=alumno.grupo).distinct()
print(f"Materias del grupo:")
for m in materias:
    print(f"  - {m.nombre}")
print()

# Calificaciones en el Trimestre 1
print("Calificaciones del alumno en el Trimestre 1:")
califs = Calificacion.objects.filter(
    alumno=alumno,
    periodo__in=periodos_t1,
    calificacion__isnull=False,
)
for c in califs:
    print(f"  Materia: {c.grupo_materia.materia.nombre} | Periodo: {c.periodo.nombre} | Calif: {c.calificacion}")
    print(f"    ¿Materia del grupo? {c.grupo_materia.materia in materias}")

print()
print("=" * 70)
print("CALIFICACIONES DEL ALUMNO (TODAS):")
print("=" * 70)
for c in Calificacion.objects.filter(alumno=alumno):
    print(f"  {c.periodo.nombre} | {c.grupo_materia.materia.nombre} | {c.calificacion}")