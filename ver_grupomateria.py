import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import GrupoMateria, Profesor, Grupo
from django.contrib.auth.models import User

print("=" * 60)
print("PROFESORES Y SUS MATERIAS ASIGNADAS")
print("=" * 60)

for p in Profesor.objects.filter(activo=True):
    gms = GrupoMateria.objects.filter(profesor=p)
    print(f"\nProfesor: {p.nombre}")
    if gms:
        for gm in gms:
            print(f"  - {gm.grupo.nombre} → {gm.materia.nombre} ({gm.horas_semanales}h)")
    else:
        print("  ⚠️  NO TIENE MATERIAS ASIGNADAS")

print()
print("=" * 60)
print("USUARIOS CON ROL PROFESOR")
print("=" * 60)

for u in User.objects.all():
    if hasattr(u, 'perfil') and u.perfil.rol == 'profesor':
        print(f"\nUsuario: {u.username}")
        if u.perfil.profesor:
            print(f"  → Vinculado a: {u.perfil.profesor.nombre}")
            gms = GrupoMateria.objects.filter(profesor=u.perfil.profesor)
            print(f"  → Materias asignadas: {gms.count()}")
            for gm in gms:
                print(f"     - {gm.grupo.nombre} → {gm.materia.nombre}")
        else:
            print("  ⚠️  NO ESTÁ VINCULADO A UN PROFESOR")