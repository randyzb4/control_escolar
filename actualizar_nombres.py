"""
Script para actualizar nombres de alumnos.
Ejecutar con: python manage.py shell < actualizar_nombres.py
"""
from horarios.models import Alumno


def parsear_nombre(texto):
    """
    Parsea un nombre en formato 'Apellido1 Apellido2 Nombre1 [Nombre2]'.
    Devuelve (nombre, apellido_paterno, apellido_materno).
    """
    tokens = texto.strip().split()
    if len(tokens) == 0:
        return '', '', ''
    elif len(tokens) == 1:
        return tokens[0], '', ''
    elif len(tokens) == 2:
        return tokens[1], tokens[0], ''
    else:
        # 3+ tokens: primeros 2 son apellidos, el resto es nombre
        apellido_paterno = tokens[0]
        apellido_materno = tokens[1]
        nombre = ' '.join(tokens[2:])
        return nombre, apellido_paterno, apellido_materno


# Lista de alumnos: (nombre_completo, grupo)
# Formato: "Apellido1 Apellido2 Nombre1 [Nombre2]"
datos = [
    # 1º A
    ("Alderete Ramírez Danna Fernanda", "1º A"),
    ("Antonio Santiago Melissa", "1º A"),
    ("Arellano Garcia Eliane Yojana", "1º A"),
    ("Angeles Franco Leonardo", "1º A"),
    ("Barete Sánchez Santiago", "1º A"),
    ("Blanco García Carlos Manuel", "1º A"),
    ("Cortes Rodriguez Mateo Sebastian", "1º A"),
    ("Cuevas García Juan pablo", "1º A"),
    ("Felipe Kusano Keigo Ramses", "1º A"),
    ("González Mendez Ian Alexander", "1º A"),
    ("Ibañez Palacios Maria Regina", "1º A"),
    ("López Aquino Ángel Alonso", "1º A"),
    ("Mendoza Gomez Mathias Gabriel", "1º A"),
    ("Morales Lira Tadeo Sebastián", "1º A"),
    ("Nuñez Torres Felix Alexander", "1º A"),
    ("Robles Bautista Sofía", "1º A"),
    ("Ruiz Martínez Aaron Alejandro", "1º A"),
    ("Santiago Santiago Valentina", "1º A"),
    ("Antonio Flores Fabián Emiliano", "1º A"),
    # 1º B
    ("Avendaño Matadamas Mateo Tristán", "1º B"),
    ("Coronado Flores Joel Eduardo", "1º B"),
    ("Cruz Paz Ana Victoria", "1º B"),
    ("Galindo García Carlos Alberto", "1º B"),
    ("Garcia Hernández Janna Itahi", "1º B"),
    ("Guendulain Sánchez Lía Constanza", "1º B"),
    ("López Álvarez Mariano Sicabi", "1º B"),
    ("Mayoral Victoria Santiago", "1º B"),
    ("Morales Gómez Rodrigo Dylan", "1º B"),
    ("Murphy Kuria Alexandra Wanjiku", "1º B"),
    ("Pérez Reyes Juan Pablo", "1º B"),
    ("Ramírez Antonio Mía", "1º B"),
    ("Reyes Herrera Mathilda", "1º B"),
    ("Sanchez Arenas Angel Xavier", "1º B"),
    ("Sanchez Belen Ariel Santiago", "1º B"),
    ("Sanchez Luis Leonardo", "1º B"),
    ("Santiago Reyes Matias Jacob", "1º B"),
    ("Solorzano Santiago Jerónimo", "1º B"),
    ("Soriano García Abraham Isaac", "1º B"),
    # 2º A
    ("Avalos Ríos Demian", "2º A"),
    ("Castellanos Olivares Ana Lis", "2º A"),
    ("Colon Jarquín Emma", "2º A"),
    ("García Aguirre Rebecca", "2º A"),
    ("García Atristaín Rubén", "2º A"),
    ("López Caballero Yaretzi", "2º A"),
    ("Hernández Santos Karla Paola", "2º A"),
    ("López Gutiérrez Sugey", "2º A"),
    ("Marini Anna Luz", "2º A"),
    ("Martínez Martínez Eduardo Antonio", "2º A"),
    ("Raymundo Ortega Josué Daniel", "2º A"),
    ("Reyes Gómez María Inés", "2º A"),
    ("Vega Ascencio Carlos Adrián", "2º A"),
    ("Zárate Cruz Luis Hassan", "2º A"),
    # 2º B
    ("Aquino Niño Alexis Santiago", "2º B"),
    ("Audiffred Figueroa Gretel", "2º B"),
    ("Cordourier Chavez Juan Carlos", "2º B"),
    ("Cruz Cortés Sofía", "2º B"),
    ("Estudillo Gonzalez Elvira", "2º B"),
    ("Martínez Domínguez Didier", "2º B"),
    ("Martínez Villanueva Iktan Emmanuel", "2º B"),
    ("Morales Morales Isis Natalia", "2º B"),
    ("Pacheco Nájera Renata Donají", "2º B"),
    ("Peralta Torres Angélica", "2º B"),
    ("Sánchez Montes Jassibe Itzayana", "2º B"),
    ("Sanchez Salinas Vanessa Alessandra", "2º B"),
    ("Santiago Jiménez Mia Constanza", "2º B"),
    # 3º A
    ("Alderete Ramírez Marina Eugenia", "3º A"),
    ("Arias Reyes Rafael Jesús", "3º A"),
    ("Carrillo Martínez Arlette Michelle", "3º A"),
    ("Cruz Gutiérrez Santiago", "3º A"),
    ("Domínguez Núñez Haley Geovanna", "3º A"),
    ("García Cruz Hansel Gadiel", "3º A"),
    ("Gutiérrez Venegas Juan Pablo", "3º A"),
    ("Hernández Fabian Aysha Kamila", "3º A"),
    ("Hernández Gonzalez Sebastian", "3º A"),
    ("Jiménez Leyva Rafael", "3º A"),
    ("Lara García André Sebastián", "3º A"),
    ("Matías Gómez Irma Sofía", "3º A"),
    ("Pérez Díaz Carlos Adrián", "3º A"),
    ("Ramírez Cruz Matías Alan", "3º A"),
    ("Ramírez Hernández Mariam Alhelí", "3º A"),
    ("Raymundo Vásquez Marco Antonio", "3º A"),
    ("Sanchez Pérez Emilio", "3º A"),
    # 3º B
    ("Acevedo Morales Gustavo Antonio", "3º B"),
    ("Alcázar Castillo Santiago", "3º B"),
    ("Arrazola García Alberto", "3º B"),
    ("Castellanos Pérez Briana Renata", "3º B"),
    ("Corral Heredia Carlos Javier", "3º B"),
    ("Cruz Hernández Gabriel", "3º B"),
    ("Guendulain Ruiz Rey Ángel", "3º B"),
    ("López Olivera Josué Damián", "3º B"),
    ("Mariscal Nuñez Luis Alberto", "3º B"),
    ("Martínez Torres Alondra Karina", "3º B"),
    ("Maya García Hannia Camila", "3º B"),
    ("Meza Chavez Santiago", "3º B"),
    ("Molina López Mateo", "3º B"),
    ("Morales Bustamante Alejandro", "3º B"),
    ("Olmedo Sarasti Julia Valentina", "3º B"),
    ("Olvera Valdovinos Alejandra Sofía", "3º B"),
    ("Ramírez Castillo Yaretzi Donají", "3º B"),
]


# ============================================================
# Proceso de actualización
# ============================================================
print("Iniciando actualización de nombres...")
print("")

actualizados = 0
no_encontrados = []
ambiguos = []

# Estrategia: buscar cada alumno por su nombre actual (que está mal)
# y actualizarlo con el nombre correcto.
#
# Como los datos actuales están en el formato:
#   nombre = "Apellido1 Apellido2"  (mal)
#   apellido_paterno = "Nombre1"    (mal)
#   apellido_materno = "Nombre2"    (mal)
#
# Vamos a buscar por la combinación de esos 3 campos.

alumnos = list(Alumno.objects.all())
print(f"Total de alumnos en BD: {len(alumnos)}")
print("")

for nombre_correcto, grupo in datos:
    nombre, paterno, materno = parsear_nombre(nombre_correcto)

    # El nombre actual en la BD está invertido. Buscamos al alumno
    # por la combinación del nombre completo actual.
    # El "nombre actual" es la combinación de apellidos + nombres que
    # están guardados al revés.
    #
    # Por ejemplo: para "Ruiz Martínez Aaron Alejandro" (correcto),
    # en la BD está como:
    #   nombre = "Ruiz Martínez"
    #   apellido_paterno = "Aaron"
    #   apellido_materno = "Alejandro"
    #
    # Así que buscamos por nombre="Ruiz Martínez" (que es paterno + materno)
    # y apellido_paterno="Aaron" (que es nombre + segundo nombre parcial).

    # Construir el nombre actual esperado
    nombre_actual_esperado = f"{paterno} {materno}".strip()
    paterno_actual_esperado = nombre  # el nombre completo actual está invertido

    # Buscar al alumno
    candidatos = alumnos
    if grupo:
        candidatos = [a for a in candidatos if a.grupo and a.grupo.nombre == grupo]

    encontrado = None
    for a in candidatos:
        # Comparar con la combinación invertida
        nombre_completo_actual = f"{a.nombre} {a.apellido_paterno} {a.apellido_materno}".strip()
        nombre_completo_esperado = nombre_correcto
        if nombre_completo_actual.lower() == nombre_completo_esperado.lower():
            encontrado = a
            break

    if encontrado:
        encontrado.nombre = nombre
        encontrado.apellido_paterno = paterno
        encontrado.apellido_materno = materno
        encontrado.save(update_fields=['nombre', 'apellido_paterno', 'apellido_materno'])
        actualizados += 1
    else:
        no_encontrados.append(f"{nombre_correcto} ({grupo})")


print("")
print("=" * 60)
print(f"Actualizados: {actualizados}")
print(f"No encontrados: {len(no_encontrados)}")
print("=" * 60)

if no_encontrados:
    print("")
    print("Alumnos no encontrados (revisar manualmente):")
    for n in no_encontrados:
        print(f"  - {n}")

if ambiguos:
    print("")
    print("Alumnos ambiguos:")
    for a in ambiguos:
        print(f"  - {a}")