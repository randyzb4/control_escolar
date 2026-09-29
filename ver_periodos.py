import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import Periodo, Calificacion

print("=" * 80)
print("ESTRUCTURA DE PERIODOS EN LA BASE DE DATOS")
print("=" * 80)

# Años escolares
print("\n📅 AÑOS ESCOLARES:")
for a in Periodo.objects.filter(tipo='anual').order_by('-fecha_inicio'):
    activo = "✅" if a.activo else "❌"
    print(f"  {activo} ID {a.id} | {a.nombre} | {a.fecha_inicio} a {a.fecha_fin}")
    print(f"      Hijos (trimestres): {[t.nombre for t in a.hijos.filter(tipo='trimestre')]}")

# Trimestres y sus periodos
print("\n📚 TRIMESTRES Y SUS PERIODOS:")
for t in Periodo.objects.filter(tipo='trimestre').order_by('fecha_inicio'):
    padre = t.padre.nombre if t.padre else "❌ SIN PADRE"
    activo = "✅" if t.activo else "❌"
    print(f"\n  {activo} ID {t.id} | {t.nombre}")
    print(f"      Padre: {padre}")
    print(f"      Fechas: {t.fecha_inicio} a {t.fecha_fin}")
    periodos_hijos = t.hijos.filter(tipo='periodo')
    print(f"      Periodos hijos ({periodos_hijos.count()}):")
    for p in periodos_hijos.order_by('fecha_inicio'):
        print(f"        - ID {p.id} | {p.nombre} | {p.fecha_inicio} a {p.fecha_fin}")

# Periodos de evaluación sin padre
print("\n📝 PERIODOS DE EVALUACIÓN SIN PADRE:")
sin_padre = Periodo.objects.filter(tipo='periodo', padre__isnull=True)
if sin_padre.exists():
    print(f"  ⚠️  {sin_padre.count()} periodos sin asignar a un trimestre:")
    for p in sin_padre:
        print(f"    - ID {p.id} | {p.nombre} | {p.fecha_inicio} a {p.fecha_fin}")
else:
    print("  ✅ Todos los periodos tienen padre asignado")

# Calificaciones por periodo
print("\n🎓 CALIFICACIONES CAPTURADAS:")
for p in Periodo.objects.filter(tipo='periodo').order_by('fecha_inicio'):
    count = Calificacion.objects.filter(periodo=p).count()
    print(f"  {p.nombre}: {count} calificaciones")

print("\n" + "=" * 80)