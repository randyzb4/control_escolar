import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_horarios.settings')
django.setup()

from horarios.models import Alumno

print("=" * 70)
print("CORRECCIÓN DE ALUMNOS CON DATOS INVERTIDOS")
print("=" * 70)

print("\nANTES:")
for a in Alumno.objects.all():
    print(f"  {a.matricula} | P: [{a.apellido_paterno}] | M: [{a.apellido_materno}] | N: [{a.nombre}]")

print("\n" + "=" * 70)
print("¿Aplicar corrección? Esta acción modificará TODOS los alumnos.")
print("Presiona ENTER para continuar o Ctrl+C para cancelar.")
input()

# Estrategia: reconstruir el nombre completo y volver a separarlo
# con la lógica correcta (apellidos primero).

for a in Alumno.objects.all():
    # Reconstruir los tokens actuales
    tokens = []
    if a.nombre:
        tokens.extend(a.nombre.split())
    if a.apellido_paterno:
        tokens.extend(a.apellido_paterno.split())
    if a.apellido_materno:
        tokens.extend(a.apellido_materno.split())

    # Como los datos están invertidos, los tokens actuales son:
    # [nombre_de_pila...] [apellido_paterno] [apellido_materno]
    # Pero el orden en BD es:
    # apellido_paterno = nombre_de_pila
    # apellido_materno = apellido_paterno
    # nombre = apellido_materno

    # La corrección es:
    ap_paterno_nuevo = a.nombre
    ap_materno_nuevo = a.apellido_paterno
    nombre_nuevo = a.apellido_materno

    # Casos especiales
    if not ap_materno_nuevo:
        # Solo 2 campos con datos
        ap_materno_nuevo = ''
        nombre_nuevo = a.apellido_paterno

    a.apellido_paterno = ap_paterno_nuevo
    a.apellido_materno = ap_materno_nuevo
    a.nombre = nombre_nuevo
    a.save()

print("\nDESPUÉS:")
for a in Alumno.objects.all():
    print(f"  {a.matricula} | P: [{a.apellido_paterno}] | M: [{a.apellido_materno}] | N: [{a.nombre}]")

print("\n✅ Corrección completada.")