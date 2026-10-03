from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.db.models import Count
from django.db import IntegrityError
from django.urls import reverse
from datetime import datetime, date, time as dt_time
from decimal import Decimal, InvalidOperation
import math
from datetime import timedelta
from .permisos import requiere_permiso, tiene_permiso
from .decorators import coordinador_requerido
from .forms import IncidenciaForm
from .utils import alumnos_para_grupo_materia
from .models import Grupo, Alumno, AlumnoSubgrupoMateria, Materia




from xhtml2pdf import pisa
from openpyxl import load_workbook, Workbook

from .services.scheduler import generar_horario
from .models import (
    Asignacion, Profesor, Grupo, GrupoMateria, SlotHorario, Materia, Aula,
    ConfiguracionHorario, Alumno, Periodo, Calificacion, Asistencia,
    Incidencia, PerfilUsuario, EvidenciaDesempeno, CalificacionEvidencia,
    Planeacion, SesionPlaneacion, EventoCalendario, ConfiguracionInstitucion,
)
from .decorators import coordinador_requerido
from .forms import IncidenciaForm


# ============================================================
#  Utilidades internas
# ============================================================
def _redondear_calificacion(valor):
    """
    Redondea una calificación al entero más cercano según la regla:
    - Decimal .0 a .4 → se queda en el entero
    - Decimal .5 a .9 → sube al entero siguiente
    - Máximo: 10
    """
    if valor is None:
        return None
    valor = float(valor)
    entero = int(valor)
    decimal = valor - entero
    if decimal >= 0.5:
        return min(entero + 1, 10)
    return entero


def _construir_grilla(asignaciones):
    dias = [1, 2, 3, 4, 5]
    nombres_dias = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes'}

    slots_unicos = (
        SlotHorario.objects
        .values_list('hora_inicio', 'hora_fin')
        .distinct()
        .order_by('hora_inicio')
    )
    horas = list(slots_unicos)

    filas = []
    for hora_inicio, hora_fin in horas:
        celdas = []
        for dia in dias:
            asignaciones_celda = []
            for a in asignaciones:
                if a.slot.hora_inicio == hora_inicio and a.slot.dia == dia:
                    asignaciones_celda.append(a)
            celdas.append(asignaciones_celda)
        filas.append({
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'celdas': celdas,
        })

    return dias, nombres_dias, filas


# ============================================================
#  Autenticación
# ============================================================

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if (hasattr(user, 'perfil')
                    and user.perfil.rol == 'profesor'
                    and user.perfil.profesor):
                return redirect('horarios:mi_horario')
            return redirect('horarios:dashboard')
        messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'horarios/login.html')


def logout_view(request):
    auth_logout(request)
    return redirect('horarios:login')


# ============================================================
#  Dashboard y generación
# ============================================================

@login_required
@requiere_permiso('dashboard', 'ver')
def dashboard(request):
    total_asignaciones = Asignacion.objects.count()
    total_profesores = Profesor.objects.filter(activo=True).count()
    total_grupos = Grupo.objects.count()
    total_materias = Materia.objects.count()
    total_aulas = Aula.objects.count()
    total_slots = SlotHorario.objects.count()

    materias_con_horas = Materia.objects.annotate(
        total_asignaciones=Count('grupomateria__asignaciones')
    ).order_by('-total_asignaciones')

    grupos_con_horas = Grupo.objects.annotate(
        total_asignaciones=Count('grupomateria__asignaciones')
    ).order_by('nombre')

    es_es_coordinador = (
        request.user.is_authenticated
        and hasattr(request.user, 'perfil')
        and request.user.perfil.rol == 'coordinador'
    )

    return render(request, 'horarios/dashboard.html', {
        'total_asignaciones': total_asignaciones,
        'total_profesores': total_profesores,
        'total_grupos': total_grupos,
        'total_materias': total_materias,
        'total_aulas': total_aulas,
        'total_slots': total_slots,
        'materias_con_horas': materias_con_horas,
        'grupos_con_horas': grupos_con_horas,
        'es_es_coordinador': es_es_coordinador,
    })


@coordinador_requerido
def ejecutar_generacion(request):
    if request.method == 'POST':
        asignadas, no_asignadas = generar_horario()
        messages.success(request, f'Se generaron {asignadas} asignaciones.')
        if no_asignadas:
            messages.warning(
                request,
                f'{len(no_asignadas)} materias no pudieron asignarse completamente.'
            )
    return redirect('horarios:dashboard')


# ============================================================
#  Grupos
# ============================================================

@login_required
@requiere_permiso('grupos', 'ver')
def lista_grupos(request):
    grupos = Grupo.objects.all().order_by('nombre')
    return render(request, 'horarios/lista_grupos.html', {'grupos': grupos})


@login_required
@requiere_permiso('grupos', 'ver')
def horario_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)
    asignaciones = Asignacion.objects.filter(
        grupo_materia__grupo=grupo
    ).select_related('grupo_materia__materia', 'profesor', 'aula', 'slot')

    dias, nombres_dias, filas = _construir_grilla(asignaciones)

    return render(request, 'horarios/horario_grupo.html', {
        'grupo': grupo,
        'dias': dias,
        'nombres_dias': nombres_dias,
        'filas': filas,
    })


@login_required
@requiere_permiso('grupos', 'ver')
def pdf_horario_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)
    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    
    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_horario_grupo.html', {
        'grupo': grupo,
        'es_profesor': es_profesor,
        'es_coordinador': es_coordinador,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="horario_{grupo.nombre}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


# ============================================================
#  Profesores
# ============================================================

@login_required
@requiere_permiso('profesores', 'ver')
def lista_profesores(request):
    profesores = Profesor.objects.filter(activo=True).order_by('nombre')
    return render(request, 'horarios/lista_profesores.html', {'profesores': profesores})


@login_required
@requiere_permiso('profesores', 'ver')
def horario_profesor(request, profesor_id):
    profesor = get_object_or_404(Profesor, pk=profesor_id)
    asignaciones = Asignacion.objects.filter(
        profesor=profesor
    ).select_related('grupo_materia__materia', 'grupo_materia__grupo', 'aula', 'slot')

    dias, nombres_dias, filas = _construir_grilla(asignaciones)

    return render(request, 'horarios/horario_profesor.html', {
        'profesor': profesor,
        'dias': dias,
        'nombres_dias': nombres_dias,
        'filas': filas,
    })


@login_required
@requiere_permiso('profesores', 'ver')
def pdf_horario_profesor(request, profesor_id):
    profesor = get_object_or_404(Profesor, pk=profesor_id)
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_horario_profesor.html', {
        'profesor': profesor,
        'es_coordinador': es_coordinador,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="horario_{profesor.nombre}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


# ============================================================
#  Reportes
# ============================================================

@login_required
@requiere_permiso('carga', 'ver')
def carga_profesores(request):
    profesores = Profesor.objects.filter(activo=True).annotate(
        total_asignaciones=Count('asignacion')
    ).order_by('-total_asignaciones')
    return render(request, 'horarios/carga_profesores.html', {'profesores': profesores})


@login_required
@requiere_permiso('resumen', 'ver')
def resumen(request):
    total_profesores = Profesor.objects.filter(activo=True).count()
    total_materias = Materia.objects.count()
    total_grupos = Grupo.objects.count()
    total_aulas = Aula.objects.count()
    total_slots = SlotHorario.objects.count()
    total_asignaciones = Asignacion.objects.count()

    materias_con_horas = Materia.objects.annotate(
        total_asignaciones=Count('grupomateria__asignaciones')
    ).order_by('-total_asignaciones')

    grupos_con_horas = Grupo.objects.annotate(
        total_asignaciones=Count('grupomateria__asignaciones')
    ).order_by('nombre')

    return render(request, 'horarios/resumen.html', {
        'total_profesores': total_profesores,
        'total_materias': total_materias,
        'total_grupos': total_grupos,
        'total_aulas': total_aulas,
        'total_slots': total_slots,
        'total_asignaciones': total_asignaciones,
        'materias_con_horas': materias_con_horas,
        'grupos_con_horas': grupos_con_horas,
    })


@login_required
@requiere_permiso('asignaciones', 'ver')
def lista_asignaciones(request):
    asignaciones = Asignacion.objects.select_related(
        'grupo_materia__grupo',
        'grupo_materia__materia',
        'profesor',
        'aula',
        'slot',
    ).order_by('slot__dia', 'slot__hora_inicio', 'grupo_materia__grupo__nombre')

    grupo_id = request.GET.get('grupo')
    materia_id = request.GET.get('materia')
    profesor_id = request.GET.get('profesor')

    if grupo_id:
        asignaciones = asignaciones.filter(grupo_materia__grupo_id=grupo_id)
    if materia_id:
        asignaciones = asignaciones.filter(grupo_materia__materia_id=materia_id)
    if profesor_id:
        asignaciones = asignaciones.filter(profesor_id=profesor_id)

    grupos = Grupo.objects.all().order_by('nombre')
    materias = Materia.objects.all().order_by('nombre')
    profesores = Profesor.objects.filter(activo=True).order_by('nombre')

    total = asignaciones.count()

    return render(request, 'horarios/lista_asignaciones.html', {
        'asignaciones': asignaciones,
        'grupos': grupos,
        'materias': materias,
        'profesores': profesores,
        'grupo_seleccionado': grupo_id or '',
        'materia_seleccionada': materia_id or '',
        'profesor_seleccionado': profesor_id or '',
        'total': total,
    })


# ============================================================
#  Configuración de horario base
# ============================================================

@coordinador_requerido
@requiere_permiso('configurar', 'ver')
def configurar_horario(request):
    config = ConfiguracionHorario.get_solo()

    if request.method == 'POST':
        hora_inicio_str = request.POST.get('hora_inicio')
        hora_fin_str = request.POST.get('hora_fin')
        duracion_bloque = request.POST.get('duracion_bloque')
        dias = request.POST.getlist('dias')
        receso1_inicio_str = request.POST.get('receso1_inicio') or None
        receso1_fin_str = request.POST.get('receso1_fin') or None
        receso2_inicio_str = request.POST.get('receso2_inicio') or None
        receso2_fin_str = request.POST.get('receso2_fin') or None

        if not dias:
            messages.error(request, 'Debes seleccionar al menos un día.')
            return redirect('horarios:configurar_horario')

        def _str_a_time(s):
            if not s:
                return None
            partes = s.split(':')
            return dt_time(int(partes[0]), int(partes[1]))

        config.hora_inicio = _str_a_time(hora_inicio_str)
        config.hora_fin = _str_a_time(hora_fin_str)
        config.duracion_bloque = int(duracion_bloque)
        config.dias_activos = ','.join(dias)
        config.receso1_inicio = _str_a_time(receso1_inicio_str)
        config.receso1_fin = _str_a_time(receso1_fin_str)
        config.receso2_inicio = _str_a_time(receso2_inicio_str)
        config.receso2_fin = _str_a_time(receso2_fin_str)
        config.save()

        total = config.generar_slots()
        messages.success(request, f'Se generaron {total} slots automáticamente.')
        return redirect('horarios:configurar_horario')

    dias_activos_ints = config.lista_dias()
    dias_disponibles = [
        {'num': num, 'nombre': nombre, 'activo': num in dias_activos_ints}
        for num, nombre in ConfiguracionHorario.DIAS_CHOICES
    ]

    slots_generados = SlotHorario.objects.count()

    return render(request, 'horarios/configurar_horario.html', {
        'config': config,
        'dias_disponibles': dias_disponibles,
        'slots_generados': slots_generados,
    })


# ============================================================
#  Portal del profesor
# ============================================================

@login_required
def mi_horario(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(
            request,
            'Tu usuario no está vinculado a un profesor. Contacta al coordinador.'
        )
        return redirect('horarios:dashboard')

    profesor = request.user.perfil.profesor

    asignaciones = Asignacion.objects.filter(
        profesor=profesor
    ).select_related(
        'grupo_materia__materia',
        'grupo_materia__grupo',
        'aula',
        'slot',
    )

    dias, nombres_dias, filas = _construir_grilla(asignaciones)

    return render(request, 'horarios/mi_horario.html', {
        'profesor': profesor,
        'dias': dias,
        'nombres_dias': nombres_dias,
        'filas': filas,
    })


@login_required
def mis_grupos(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Tu usuario no está vinculado a un profesor.')
        return redirect('horarios:dashboard')

    profesor = request.user.perfil.profesor

    grupos = Grupo.objects.filter(
        grupomateria__profesor=profesor
    ).annotate(
        num_alumnos=Count('alumnos', distinct=True)
    ).distinct().order_by('nombre')

    grupos_con_materias = []
    for grupo in grupos:
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo,
            grupomateria__profesor=profesor
        ).distinct()
        grupos_con_materias.append({
            'grupo': grupo,
            'materias': materias,
        })

    return render(request, 'horarios/mis_grupos.html', {
        'profesor': profesor,
        'grupos_con_materias': grupos_con_materias,
    })


@login_required
def capturar_calificaciones(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Tu usuario no está vinculado a un profesor.')
        return redirect('horarios:dashboard')

    profesor = request.user.perfil.profesor
    grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
    periodos = Periodo.objects.filter(activo=True, tipo='periodo').order_by('-fecha_inicio')

    # Leer parámetros de GET o POST
    grupo_id = request.POST.get('grupo') or request.GET.get('grupo')
    materia_id = request.POST.get('materia') or request.GET.get('materia')
    periodo_id = request.POST.get('periodo') or request.GET.get('periodo')

    # Calcular materias SIEMPRE que haya grupo seleccionado
    materias = []
    if grupo_id:
        materias = Materia.objects.filter(
            grupomateria__grupo_id=grupo_id,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')

    # --- POST: guardar calificaciones ---
    if request.method == 'POST':
        if not grupo_id or not materia_id or not periodo_id:
            messages.error(request, 'Debes seleccionar grupo, materia y periodo.')
            return redirect('horarios:capturar_calificaciones')

        gm = GrupoMateria.objects.get(
            grupo_id=grupo_id, materia_id=materia_id, profesor=profesor
        )
        periodo = Periodo.objects.get(id=periodo_id)

        # Filtrar alumnos por subgrupo del GrupoMateria
        alumnos_qs = alumnos_para_grupo_materia(gm)

        for alumno in alumnos_qs:
            valor = request.POST.get(f'calif_{alumno.id}')
            if valor:
                try:
                    calif = Decimal(valor.replace(',', '.'))
                    Calificacion.objects.update_or_create(
                        alumno=alumno,
                        grupo_materia=gm,
                        periodo=periodo,
                        defaults={'calificacion': calif, 'capturada_por': request.user}
                    )
                except InvalidOperation:
                    continue

        messages.success(request, 'Calificaciones guardadas.')
        return redirect(
            f"{reverse('horarios:capturar_calificaciones')}"
            f"?grupo={grupo_id}&materia={materia_id}&periodo={periodo_id}"
        )

    # --- GET: mostrar alumnos y calificaciones ---
    alumnos_con_calif = []

    if grupo_id and materia_id and periodo_id:
        gm = GrupoMateria.objects.get(
            grupo_id=grupo_id, materia_id=materia_id, profesor=profesor
        )
        periodo = Periodo.objects.get(id=periodo_id)

        # Filtrar alumnos por subgrupo del GrupoMateria
        alumnos = alumnos_para_grupo_materia(gm)

        calificaciones = Calificacion.objects.filter(
            grupo_materia=gm, periodo=periodo
        )
        calif_dict = {c.alumno_id: c for c in calificaciones}

        alumnos_con_calif = [(a, calif_dict.get(a.id)) for a in alumnos]

    return render(request, 'horarios/capturar_calificaciones.html', {
        'grupos': grupos,
        'materias': materias,
        'periodos': periodos,
        'grupo_sel': grupo_id or '',
        'materia_sel': materia_id or '',
        'periodo_sel': periodo_id or '',
        'alumnos_con_calif': alumnos_con_calif,
    })


@login_required
def pase_lista(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Tu usuario no está vinculado a un profesor.')
        return redirect('horarios:dashboard')

    profesor = request.user.perfil.profesor
    grupos = Grupo.objects.filter(
        grupomateria__profesor=profesor
    ).distinct().order_by('nombre')

    # Leer parámetros de GET o POST
    grupo_id = request.POST.get('grupo') or request.GET.get('grupo')
    materia_id = request.POST.get('materia') or request.GET.get('materia')
    fecha_str = request.POST.get('fecha') or request.GET.get('fecha')

    # Calcular materias SIEMPRE que haya grupo seleccionado
    materias = []
    if grupo_id:
        materias = Materia.objects.filter(
            grupomateria__grupo_id=grupo_id,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')

    # --- POST: guardar asistencia ---
    if request.method == 'POST':
        if not grupo_id or not materia_id or not fecha_str:
            messages.error(request, 'Debes seleccionar grupo, materia y fecha.')
            return redirect('horarios:pase_lista')

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fecha inválida.')
            return redirect('horarios:pase_lista')

        gm = GrupoMateria.objects.get(
            grupo_id=grupo_id, materia_id=materia_id, profesor=profesor
        )

        # Filtrar alumnos por subgrupo del GrupoMateria
        alumnos_qs = alumnos_para_grupo_materia(gm)

        for alumno in alumnos_qs:
            estado = request.POST.get(f'estado_{alumno.id}', 'presente')
            obs = request.POST.get(f'obs_{alumno.id}', '')
            Asistencia.objects.update_or_create(
                alumno=alumno,
                grupo_materia=gm,
                fecha=fecha,
                defaults={
                    'estado': estado,
                    'observaciones': obs,
                    'registrada_por': request.user,
                }
            )

        messages.success(request, 'Asistencia guardada.')
        return redirect(
            f"{reverse('horarios:pase_lista')}"
            f"?grupo={grupo_id}&materia={materia_id}&fecha={fecha_str}"
        )

    # --- GET: mostrar alumnos ---
    alumnos_con_asist = []

    if grupo_id and materia_id and fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = None

        if fecha:
            gm = GrupoMateria.objects.get(
                grupo_id=grupo_id, materia_id=materia_id, profesor=profesor
            )
            # Filtrar alumnos por subgrupo del GrupoMateria
            alumnos = alumnos_para_grupo_materia(gm)

            asistencias = Asistencia.objects.filter(
                grupo_materia=gm, fecha=fecha
            )
            asist_dict = {a.alumno_id: a for a in asistencias}

            alumnos_con_asist = [(a, asist_dict.get(a.id)) for a in alumnos]

    return render(request, 'horarios/pase_lista.html', {
        'grupos': grupos,
        'materias': materias,
        'grupo_sel': grupo_id or '',
        'materia_sel': materia_id or '',
        'fecha_sel': fecha_str or '',
        'alumnos_con_asist': alumnos_con_asist,
        'hoy': date.today().isoformat(),
    })


@login_required
def mi_bitacora(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Tu usuario no está vinculado a un profesor.')
        return redirect('horarios:dashboard')
    return render(request, 'horarios/mi_bitacora.html', {})


# ============================================================
#  Carga masiva de alumnos desde Excel
# ============================================================

@login_required
@coordinador_requerido
def cargar_alumnos(request):
    if request.method == 'POST':
        if 'archivo' not in request.FILES:
            messages.error(request, 'No seleccionaste ningún archivo.')
            return redirect('horarios:cargar_alumnos')

        archivo = request.FILES['archivo']

        if not archivo.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser .xlsx o .xls')
            return redirect('horarios:cargar_alumnos')

        try:
            wb = load_workbook(archivo, data_only=True)
            hoja = wb.active

            encabezados = []
            for celda in hoja[1]:
                if celda.value:
                    encabezados.append(str(celda.value).strip().lower().replace(' ', '_'))
                else:
                    encabezados.append('')

            tiene_separado = 'apellido_paterno' in encabezados

            creados = 0
            actualizados = 0
            errores = []

            for idx, fila in enumerate(hoja.iter_rows(min_row=2, values_only=True), start=2):
                if not fila or not fila[0]:
                    continue

                datos = {}
                for i, enc in enumerate(encabezados):
                    if i < len(fila):
                        datos[enc] = fila[i]

                matricula = str(datos.get('matricula', '')).strip()
                grupo_nombre = str(datos.get('grupo', '')).strip()
                email = str(datos.get('email', '')).strip() if datos.get('email') else ''
                subgrupo = str(datos.get('subgrupo', '')).strip() if datos.get('subgrupo') else ''

                if subgrupo not in ('1', '2', ''):
                    subgrupo = ''

                if not matricula or not grupo_nombre:
                    errores.append(f'Fila {idx}: faltan matrícula o grupo.')
                    continue

                grupo = Grupo.objects.filter(nombre=grupo_nombre).first()
                if not grupo:
                    errores.append(f'Fila {idx}: grupo "{grupo_nombre}" no existe.')
                    continue

                if tiene_separado:
                    nombre = str(datos.get('nombre', '')).strip()
                    apellido_paterno = str(datos.get('apellido_paterno', '')).strip()
                    apellido_materno = str(datos.get('apellido_materno', '')).strip() if datos.get('apellido_materno') else ''
                else:
                    nombre_completo = str(datos.get('nombre_completo', '')).strip()
                    if not nombre_completo:
                        errores.append(f'Fila {idx}: falta el nombre.')
                        continue

                    tokens = nombre_completo.split()
                    if len(tokens) == 1:
                        nombre = tokens[0]
                        apellido_paterno = ''
                        apellido_materno = ''
                    elif len(tokens) == 2:
                        nombre = tokens[0]
                        apellido_paterno = tokens[1]
                        apellido_materno = ''
                    else:
                        nombre = ' '.join(tokens[:-2])
                        apellido_paterno = tokens[-2]
                        apellido_materno = tokens[-1]

                alumno, created = Alumno.objects.update_or_create(
                    matricula=matricula,
                    defaults={
                        'nombre': nombre,
                        'apellido_paterno': apellido_paterno,
                        'apellido_materno': apellido_materno,
                        'email': email,
                        'grupo': grupo,
                        'subgrupo': subgrupo,
                        'activo': True,
                    }
                )

                if created:
                    creados += 1
                else:
                    actualizados += 1

            mensaje = f'Carga completada: {creados} creados, {actualizados} actualizados.'
            if errores:
                mensaje += f' {len(errores)} errores.'
                for e in errores[:5]:
                    messages.warning(request, e)

            messages.success(request, mensaje)
            return redirect('horarios:cargar_alumnos')

        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            return redirect('horarios:cargar_alumnos')

    return render(request, 'horarios/cargar_alumnos.html', {})


@login_required
@coordinador_requerido
def descargar_plantilla_alumnos(request):
    wb = Workbook()

    # Hoja 1 - Formato A
    hoja_a = wb.active
    hoja_a.title = 'Formato A (separado)'
    hoja_a.append(['matricula', 'nombre', 'apellido_paterno', 'apellido_materno', 'grupo', 'subgrupo', 'email'])
    hoja_a.append(['2026001', 'Juan', 'Pérez', 'López', '1° A', '1', 'juan@ejemplo.com'])
    hoja_a.append(['2026002', 'María', 'García', 'Ruiz', '1° A', '2', 'maria@ejemplo.com'])

    # Hoja 2 - Formato B
    hoja_b = wb.create_sheet('Formato B (junto)')
    hoja_b.append(['matricula', 'nombre_completo', 'grupo', 'subgrupo', 'email'])
    hoja_b.append(['2026001', 'Juan Pérez López', '1° A', '1', 'juan@ejemplo.com'])
    hoja_b.append(['2026002', 'María García Ruiz', '1° A', '2', 'maria@ejemplo.com'])

    # Hoja 3 - Instrucciones
    hoja_c = wb.create_sheet('Instrucciones')
    hoja_c.append(['Instrucciones para la carga de alumnos'])
    hoja_c.append([])
    hoja_c.append(['1. La columna subgrupo es opcional.'])
    hoja_c.append(['2. Valores permitidos en subgrupo: 1, 2, o dejar vacío.'])
    hoja_c.append(['3. El subgrupo se usa para materias paralelas (ej: Inglés Nivel 1 vs Nivel 2).'])
    hoja_c.append(['4. Los alumnos del subgrupo 1 van con el profesor de la materia paralela que corresponda.'])
    hoja_c.append(['5. Puedes mezclar alumnos de distintos grupos en el mismo archivo.'])
    hoja_c.append([])
    hoja_c.append(['Columnas por hoja:'])
    hoja_c.append(['  Formato A: matricula, nombre, apellido_paterno, apellido_materno, grupo, subgrupo, email'])
    hoja_c.append(['  Formato B: matricula, nombre_completo, grupo, subgrupo, email'])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_alumnos.xlsx"'
    wb.save(response)
    return response


@login_required
def boleta_alumno(request, alumno_id):
    """Muestra la boleta de un alumno con filtro y fusión de materias paralelas."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=alumno.grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso para ver esta boleta.')
        return redirect('horarios:dashboard')

    anio_escolar = Periodo.objects.filter(tipo='anual', activo=True).order_by('-fecha_inicio').first()
    if not anio_escolar:
        anio_escolar = Periodo.objects.filter(tipo='anual').order_by('-fecha_inicio').first()

    if not anio_escolar:
        messages.warning(request, 'No hay un año escolar configurado.')
        return redirect('horarios:dashboard')

    trimestres = anio_escolar.hijos.filter(tipo='trimestre').order_by('fecha_inicio')
    trimestres_ids = list(trimestres.values_list('id', flat=True))
    periodos = Periodo.objects.filter(
        tipo='periodo', padre_id__in=trimestres_ids
    ).order_by('fecha_inicio')

        # Serializables para json_script
    periodos_json = [
        {
            'id': p.id,
            'nombre': p.nombre,
            'tipo': p.tipo,
            'fecha_inicio': p.fecha_inicio.isoformat() if p.fecha_inicio else None,
            'fecha_fin': p.fecha_fin.isoformat() if p.fecha_fin else None,
        }
        for p in periodos
    ]

    trimestres_json = [
        {
            'id': t.id,
            'nombre': t.nombre,
            'tipo': t.tipo,
            'fecha_inicio': t.fecha_inicio.isoformat() if t.fecha_inicio else None,
            'fecha_fin': t.fecha_fin.isoformat() if t.fecha_fin else None,
        }
        for t in trimestres
    ]

    # Obtener todas las materias del grupo del alumno
    materias_raw = Materia.objects.filter(
        grupomateria__grupo=alumno.grupo
    ).distinct().order_by('nombre')

    # Agrupar por nombre_boleta (fusiona materias paralelas)
    grupos_por_nombre = {}
    for m in materias_raw:
        nombre = m.nombre_boleta()
        if nombre not in grupos_por_nombre:
            grupos_por_nombre[nombre] = []
        grupos_por_nombre[nombre].append(m)

    # Construir lista de materias únicas para el template
    materias_unicas = []
    for nombre_boleta, grupo_materias in sorted(grupos_por_nombre.items()):
        materias_unicas.append({
            'nombre': nombre_boleta,
            'materia_ids': [m.id for m in grupo_materias],
        })

    tipo_sel = request.GET.get('tipo', '')
    id_sel = request.GET.get('id', '')

    # Inicializar variables
    columnas = []
    filas = []
    promedios_extra = []
    promedio_general = None
    periodo_sel = None
    trimestre_sel = None

    if tipo_sel == 'periodo' and id_sel:
        periodo_sel = Periodo.objects.filter(pk=id_sel).first()
        if periodo_sel:
            columnas = [periodo_sel]
            for mat in materias_unicas:
                calif = Calificacion.objects.filter(
                    alumno=alumno,
                    grupo_materia__materia_id__in=mat['materia_ids'],
                    periodo=periodo_sel,
                    calificacion__isnull=False
                ).first()
                valor = _redondear_calificacion(calif.calificacion) if calif else None
                filas.append({
                    'materia': mat['nombre'],
                    'calificacion': valor,
                })
        else:
            messages.error(request, 'Periodo no encontrado.')
            return redirect('horarios:boleta_alumno', alumno_id=alumno.id)

    elif tipo_sel == 'trimestre' and id_sel:
        trimestre_sel = Periodo.objects.filter(pk=id_sel).first()
        if trimestre_sel:
            columnas = list(trimestre_sel.hijos.filter(tipo='periodo').order_by('fecha_inicio'))
            for mat in materias_unicas:
                califs_periodo = []
                suma_materia = 0
                cuenta_materia = 0
                for p in columnas:
                    calif = Calificacion.objects.filter(
                        alumno=alumno,
                        grupo_materia__materia_id__in=mat['materia_ids'],
                        periodo=p,
                        calificacion__isnull=False
                    ).first()
                    valor = _redondear_calificacion(calif.calificacion) if calif else None
                    califs_periodo.append(valor)
                    if valor is not None:
                        suma_materia += valor
                        cuenta_materia += 1

                promedio_materia = _redondear_calificacion(suma_materia / cuenta_materia) if cuenta_materia > 0 else None
                filas.append({
                    'materia': mat['nombre'],
                    'calificaciones': califs_periodo,
                    'promedio': promedio_materia,
                })

            # Promedio por periodo
            promedios_extra = []
            for i in range(len(columnas)):
                valores = [f['calificaciones'][i] for f in filas if f['calificaciones'][i] is not None]
                promedios_extra.append(_redondear_calificacion(sum(valores) / len(valores)) if valores else None)

            # Promedio general del trimestre
            valores_prom = [f['promedio'] for f in filas if f['promedio'] is not None]
            promedio_general = _redondear_calificacion(sum(valores_prom) / len(valores_prom)) if valores_prom else None
        else:
            messages.error(request, 'Trimestre no encontrado.')
            return redirect('horarios:boleta_alumno', alumno_id=alumno.id)

    elif tipo_sel == 'final':
        for mat in materias_unicas:
            trimestres_promedios = []
            for t in trimestres:
                periodos_eval = t.hijos.filter(tipo='periodo').order_by('fecha_inicio')
                califs = Calificacion.objects.filter(
                    alumno=alumno,
                    grupo_materia__materia_id__in=mat['materia_ids'],
                    periodo__in=periodos_eval,
                    calificacion__isnull=False
                )
                if califs.exists():
                    promedio = _redondear_calificacion(
                        sum(float(c.calificacion) for c in califs) / califs.count()
                    )
                    trimestres_promedios.append(promedio)
                else:
                    trimestres_promedios.append(None)

            valores_validos = [v for v in trimestres_promedios if v is not None]
            promedio_final = _redondear_calificacion(sum(valores_validos) / len(valores_validos)) if valores_validos else None

            filas.append({
                'materia': mat['nombre'],
                'trimestres': trimestres_promedios,
                'promedio_final': promedio_final,
            })

        # Promedio por trimestre
        promedios_extra = []
        for i in range(len(trimestres)):
            valores = [f['trimestres'][i] for f in filas if f['trimestres'][i] is not None]
            promedios_extra.append(_redondear_calificacion(sum(valores) / len(valores)) if valores else None)

        # Promedio general final
        valores_finales = [f['promedio_final'] for f in filas if f['promedio_final'] is not None]
        promedio_general = _redondear_calificacion(sum(valores_finales) / len(valores_finales)) if valores_finales else None

        columnas = list(trimestres)

    config_inst = ConfiguracionInstitucion.get_solo()

    return render(request, 'horarios/boleta_alumno.html', {
        'alumno': alumno,
        'anio_escolar': anio_escolar,
        'trimestres': trimestres,
        'periodos': periodos,
        'trimestres_json': trimestres_json,   # ← NUEVO
        'periodos_json': periodos_json,       # ← NUEVO
        'tipo_sel': tipo_sel,
        'id_sel': id_sel,
        'columnas': columnas,
        'filas': filas,
        'promedios_extra': promedios_extra,
        'promedio_general': promedio_general,
        'periodo_sel': periodo_sel,
        'trimestre_sel': trimestre_sel,
        'config_institucion': config_inst,
    })


@login_required
def pdf_boleta_alumno(request, alumno_id):
    """Genera PDF de la boleta de un alumno con filtro y fusión de materias paralelas."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=alumno.grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:dashboard')

    anio_escolar = Periodo.objects.filter(tipo='anual', activo=True).order_by('-fecha_inicio').first()
    if not anio_escolar:
        anio_escolar = Periodo.objects.filter(tipo='anual').order_by('-fecha_inicio').first()

    if not anio_escolar:
        messages.warning(request, 'No hay un año escolar configurado.')
        return redirect('horarios:dashboard')

    trimestres = anio_escolar.hijos.filter(tipo='trimestre').order_by('fecha_inicio')
    trimestres_ids = list(trimestres.values_list('id', flat=True))
    periodos = Periodo.objects.filter(
        tipo='periodo', padre_id__in=trimestres_ids
    ).order_by('fecha_inicio')

    # Serializables para json_script
    periodos_json = [
       {
         'id': p.id,
         'nombre': p.nombre,
         'tipo': p.tipo,
         'fecha_inicio': p.fecha_inicio.isoformat() if p.fecha_inicio else None,
         'fecha_fin': p.fecha_fin.isoformat() if p.fecha_fin else None,
       }
       for p in periodos
]

    trimestres_json = [
        {
        'id': t.id,
        'nombre': t.nombre,
        'tipo': t.tipo,
        'fecha_inicio': t.fecha_inicio.isoformat() if t.fecha_inicio else None,
        'fecha_fin': t.fecha_fin.isoformat() if t.fecha_fin else None,
         }
       for t in trimestres
]

    # Agrupar materias paralelas
    materias_raw = Materia.objects.filter(
        grupomateria__grupo=alumno.grupo
    ).distinct().order_by('nombre')

    grupos_por_nombre = {}
    for m in materias_raw:
        nombre = m.nombre_boleta()
        if nombre not in grupos_por_nombre:
            grupos_por_nombre[nombre] = []
        grupos_por_nombre[nombre].append(m)

    materias_unicas = []
    for nombre_boleta, grupo_materias in sorted(grupos_por_nombre.items()):
        materias_unicas.append({
            'nombre': nombre_boleta,
            'materia_ids': [m.id for m in grupo_materias],
        })

    tipo_sel = request.GET.get('tipo', '')
    id_sel = request.GET.get('id', '')

    columnas = []
    filas = []
    promedios_extra = []
    promedio_general = None
    periodo_sel = None
    trimestre_sel = None

    if tipo_sel == 'periodo' and id_sel:
        periodo_sel = Periodo.objects.filter(pk=id_sel).first()
        if periodo_sel:
            columnas = [periodo_sel]
            for mat in materias_unicas:
                calif = Calificacion.objects.filter(
                    alumno=alumno,
                    grupo_materia__materia_id__in=mat['materia_ids'],
                    periodo=periodo_sel,
                    calificacion__isnull=False
                ).first()
                valor = _redondear_calificacion(calif.calificacion) if calif else None
                filas.append({
                    'materia': mat['nombre'],
                    'calificacion': valor,
                })

    elif tipo_sel == 'trimestre' and id_sel:
        trimestre_sel = Periodo.objects.filter(pk=id_sel).first()
        if trimestre_sel:
            columnas = list(trimestre_sel.hijos.filter(tipo='periodo').order_by('fecha_inicio'))
            for mat in materias_unicas:
                califs_periodo = []
                suma_materia = 0
                cuenta_materia = 0
                for p in columnas:
                    calif = Calificacion.objects.filter(
                        alumno=alumno,
                        grupo_materia__materia_id__in=mat['materia_ids'],
                        periodo=p,
                        calificacion__isnull=False
                    ).first()
                    valor = _redondear_calificacion(calif.calificacion) if calif else None
                    califs_periodo.append(valor)
                    if valor is not None:
                        suma_materia += valor
                        cuenta_materia += 1

                promedio_materia = _redondear_calificacion(suma_materia / cuenta_materia) if cuenta_materia > 0 else None
                filas.append({
                    'materia': mat['nombre'],
                    'calificaciones': califs_periodo,
                    'promedio': promedio_materia,
                })

            promedios_extra = []
            for i in range(len(columnas)):
                valores = [f['calificaciones'][i] for f in filas if f['calificaciones'][i] is not None]
                promedios_extra.append(_redondear_calificacion(sum(valores) / len(valores)) if valores else None)

            valores_prom = [f['promedio'] for f in filas if f['promedio'] is not None]
            promedio_general = _redondear_calificacion(sum(valores_prom) / len(valores_prom)) if valores_prom else None

    elif tipo_sel == 'final':
        for mat in materias_unicas:
            trimestres_promedios = []
            for t in trimestres:
                periodos_eval = t.hijos.filter(tipo='periodo').order_by('fecha_inicio')
                califs = Calificacion.objects.filter(
                    alumno=alumno,
                    grupo_materia__materia_id__in=mat['materia_ids'],
                    periodo__in=periodos_eval,
                    calificacion__isnull=False
                )
                if califs.exists():
                    promedio = _redondear_calificacion(
                        sum(float(c.calificacion) for c in califs) / califs.count()
                    )
                    trimestres_promedios.append(promedio)
                else:
                    trimestres_promedios.append(None)

            valores_validos = [v for v in trimestres_promedios if v is not None]
            promedio_final = _redondear_calificacion(sum(valores_validos) / len(valores_validos)) if valores_validos else None

            filas.append({
                'materia': mat['nombre'],
                'trimestres': trimestres_promedios,
                'promedio_final': promedio_final,
            })

        promedios_extra = []
        for i in range(len(trimestres)):
            valores = [f['trimestres'][i] for f in filas if f['trimestres'][i] is not None]
            promedios_extra.append(_redondear_calificacion(sum(valores) / len(valores)) if valores else None)

        valores_finales = [f['promedio_final'] for f in filas if f['promedio_final'] is not None]
        promedio_general = _redondear_calificacion(sum(valores_finales) / len(valores_finales)) if valores_finales else None

        columnas = list(trimestres)

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_boleta_alumno.html', {
        'alumno': alumno,
        'anio_escolar': anio_escolar,
        'trimestres': trimestres,
        'periodos': periodos,
        'tipo_sel': tipo_sel,
        'id_sel': id_sel,
        'columnas': columnas,
        'filas': filas,
        'promedios_extra': promedios_extra,
        'promedio_general': promedio_general,
        'periodo_sel': periodo_sel,
        'trimestre_sel': trimestre_sel,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleta_{alumno.matricula}_{tipo_sel}_{id_sel}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response




@login_required
@requiere_permiso('grupos', 'ver')
def lista_alumnos_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)
    alumnos = Alumno.objects.filter(grupo=grupo, activo=True).order_by(
        'apellido_paterno', 'apellido_materno', 'nombre'
    )
    return render(request, 'horarios/lista_alumnos_grupo.html', {
        'grupo': grupo,
        'alumnos': alumnos,
    })


@login_required
def materias_por_grupo(request):
    grupo_id = request.GET.get('grupo')

    if not grupo_id:
        return JsonResponse({'materias': []})

    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    # Auxiliares y otros roles: validar por permisos granulares
    if not (es_profesor or es_coordinador):
        if not (tiene_permiso(request.user, 'grupos', 'ver') or
                tiene_permiso(request.user, 'desempeno', 'ver')):
            return JsonResponse({'materias': []})

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        materias = Materia.objects.filter(
            grupomateria__grupo_id=grupo_id,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')
    else:
        materias = Materia.objects.filter(
            grupomateria__grupo_id=grupo_id
        ).distinct().order_by('nombre')

    data = [{'id': m.id, 'nombre': m.nombre} for m in materias]
    return JsonResponse({'materias': data})


@login_required
def calificaciones_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso para ver este grupo.')
        return redirect('horarios:dashboard')

    # Periodo seleccionado (el más reciente activo por defecto)
    periodos = Periodo.objects.filter(activo=True, tipo='periodo').order_by('-fecha_inicio')
    periodo_id = request.GET.get('periodo')
    periodo_sel = None

    if periodo_id:
        try:
            periodo_sel = Periodo.objects.get(pk=periodo_id)
        except Periodo.DoesNotExist:
            periodo_sel = None

    if not periodo_sel and periodos.exists():
        periodo_sel = periodos.first()

    # Materias: profesor ve solo las suyas, coordinador ve todas
    if es_profesor_del_grupo and not es_coordinador:
        profesor = request.user.perfil.profesor
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')
    else:
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo
        ).distinct().order_by('nombre')

    # Alumnos del grupo
    alumnos = Alumno.objects.filter(
        grupo=grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    # Calificaciones del periodo seleccionado
    calificaciones = {}
    if periodo_sel:
        for c in Calificacion.objects.filter(
            alumno__grupo=grupo,
            periodo=periodo_sel,
            calificacion__isnull=False,
        ).select_related('grupo_materia__materia'):
            calificaciones[(c.alumno_id, c.grupo_materia.materia_id)] = c.calificacion

    # Construir filas: cada fila es un alumno con sus calificaciones y promedio
    filas = []
    promedios_materia = {}
    suma_general = 0
    cuenta_general = 0

    for a in alumnos:
        cals = []
        suma_alumno = 0
        cuenta_alumno = 0

        for m in materias:
            calif = calificaciones.get((a.id, m.id))
            cals.append(calif)
            if calif is not None:
                suma_alumno += float(calif)
                cuenta_alumno += 1

                if m.id not in promedios_materia:
                    promedios_materia[m.id] = [0, 0]
                promedios_materia[m.id][0] += float(calif)
                promedios_materia[m.id][1] += 1

        promedio_alumno = _redondear_calificacion(suma_alumno / cuenta_alumno) if cuenta_alumno > 0 else None

        if promedio_alumno is not None:
            suma_general += suma_alumno
            cuenta_general += cuenta_alumno

        filas.append({
            'alumno': a,
            'calificaciones': cals,
            'promedio': promedio_alumno,
        })

    # Promedios por materia
    promedios_mat = []
    for m in materias:
        datos = promedios_materia.get(m.id)
        if datos and datos[1] > 0:
            promedios_mat.append(_redondear_calificacion(datos[0] / datos[1]))
        else:
            promedios_mat.append(None)

    promedio_general = _redondear_calificacion(suma_general / cuenta_general) if cuenta_general > 0 else None

    return render(request, 'horarios/calificaciones_grupo.html', {
        'grupo': grupo,
        'periodos': periodos,
        'periodo_sel': periodo_sel,
        'materias': materias,
        'filas': filas,
        'promedios_materia': promedios_mat,
        'promedio_general': promedio_general,
        'es_coordinador': es_coordinador,
        'es_profesor': es_profesor_del_grupo,
    })



@login_required
def pdf_calificaciones_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:dashboard')

    periodos = Periodo.objects.filter(activo=True, tipo='periodo').order_by('-fecha_inicio')
    periodo_id = request.GET.get('periodo')
    periodo_sel = None

    if periodo_id:
        try:
            periodo_sel = Periodo.objects.get(pk=periodo_id)
        except Periodo.DoesNotExist:
            periodo_sel = None

    if not periodo_sel and periodos.exists():
        periodo_sel = periodos.first()

    # Materias: profesor ve solo las suyas, coordinador ve todas
    if es_profesor_del_grupo and not es_coordinador:
        profesor = request.user.perfil.profesor
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')
    else:
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo
        ).distinct().order_by('nombre')

    alumnos = Alumno.objects.filter(
        grupo=grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    calificaciones = {}
    if periodo_sel:
        for c in Calificacion.objects.filter(
            alumno__grupo=grupo,
            periodo=periodo_sel,
            calificacion__isnull=False,
        ).select_related('grupo_materia__materia'):
            calificaciones[(c.alumno_id, c.grupo_materia.materia_id)] = c.calificacion

    filas = []
    promedios_materia = {}
    suma_general = 0
    cuenta_general = 0

    for a in alumnos:
        cals = []
        suma_alumno = 0
        cuenta_alumno = 0

        for m in materias:
            calif = calificaciones.get((a.id, m.id))
            cals.append(calif)
            if calif is not None:
                suma_alumno += float(calif)
                cuenta_alumno += 1

                if m.id not in promedios_materia:
                    promedios_materia[m.id] = [0, 0]
                promedios_materia[m.id][0] += float(calif)
                promedios_materia[m.id][1] += 1

        promedio_alumno = _redondear_calificacion(suma_alumno / cuenta_alumno) if cuenta_alumno > 0 else None

        if promedio_alumno is not None:
            suma_general += suma_alumno
            cuenta_general += cuenta_alumno

        filas.append({
            'alumno': a,
            'calificaciones': cals,
            'promedio': promedio_alumno,
        })

    promedios_mat = []
    for m in materias:
        datos = promedios_materia.get(m.id)
        if datos and datos[1] > 0:
            promedios_mat.append(_redondear_calificacion(datos[0] / datos[1]))
        else:
            promedios_mat.append(None)

    promedio_general = _redondear_calificacion(suma_general / cuenta_general) if cuenta_general > 0 else None

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_calificaciones_grupo.html', {
        'grupo': grupo,
        'periodo_sel': periodo_sel,
        'materias': materias,
        'filas': filas,
        'promedios_materia': promedios_mat,
        'promedio_general': promedio_general,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    periodo_nombre = periodo_sel.nombre.replace(' ', '_') if periodo_sel else 'sin_periodo'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="calificaciones_{grupo.nombre}_{periodo_nombre}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


@login_required
@requiere_permiso('asistencias_grupo', 'ver')
def asistencias_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=grupo, profesor=profesor
        ).exists()

    

    materias = Materia.objects.filter(
        grupomateria__grupo=grupo
    ).distinct().order_by('nombre')

    materia_id = request.GET.get('materia')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    materia_sel = None
    if materia_id:
        try:
            materia_sel = Materia.objects.get(pk=materia_id)
        except Materia.DoesNotExist:
            materia_sel = None

    alumnos = Alumno.objects.filter(
        grupo=grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    asistencias_qs = Asistencia.objects.filter(
        alumno__grupo=grupo
    ).select_related('alumno', 'grupo_materia__materia')

    if materia_sel:
        asistencias_qs = asistencias_qs.filter(grupo_materia__materia=materia_sel)

    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            asistencias_qs = asistencias_qs.filter(fecha__gte=fecha_inicio)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            asistencias_qs = asistencias_qs.filter(fecha__lte=fecha_fin)
        except ValueError:
            pass

    resumen = []
    for a in alumnos:
        asists = asistencias_qs.filter(alumno=a)
        presente = asists.filter(estado='presente').count()
        ausente = asists.filter(estado='ausente').count()
        retardo = asists.filter(estado='retardo').count()
        justificado = asists.filter(estado='justificado').count()
        total = presente + ausente + retardo + justificado

        asistio = presente + retardo + justificado
        porcentaje = (asistio / total * 100) if total > 0 else None

        resumen.append({
            'alumno': a,
            'presente': presente,
            'ausente': ausente,
            'retardo': retardo,
            'justificado': justificado,
            'total': total,
            'porcentaje': porcentaje,
        })

    return render(request, 'horarios/asistencias_grupo.html', {
        'grupo': grupo,
        'materias': materias,
        'materia_sel': materia_sel,
        'fecha_inicio': fecha_inicio_str or '',
        'fecha_fin': fecha_fin_str or '',
        'resumen': resumen,
    })


@login_required
@requiere_permiso('asistencias_grupo', 'ver')
def pdf_asistencias_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=grupo, profesor=profesor
        ).exists()

    

    materia_id = request.GET.get('materia')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    materia_sel = None
    if materia_id:
        try:
            materia_sel = Materia.objects.get(pk=materia_id)
        except Materia.DoesNotExist:
            materia_sel = None

    alumnos = Alumno.objects.filter(
        grupo=grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    asistencias_qs = Asistencia.objects.filter(alumno__grupo=grupo)

    if materia_sel:
        asistencias_qs = asistencias_qs.filter(grupo_materia__materia=materia_sel)
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            asistencias_qs = asistencias_qs.filter(fecha__gte=fecha_inicio)
        except ValueError:
            pass
    if fecha_fin_str:
        try:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            asistencias_qs = asistencias_qs.filter(fecha__lte=fecha_fin)
        except ValueError:
            pass

    resumen = []
    for a in alumnos:
        asists = asistencias_qs.filter(alumno=a)
        presente = asists.filter(estado='presente').count()
        ausente = asists.filter(estado='ausente').count()
        retardo = asists.filter(estado='retardo').count()
        justificado = asists.filter(estado='justificado').count()
        total = presente + ausente + retardo + justificado
        asistio = presente + retardo + justificado
        porcentaje = (asistio / total * 100) if total > 0 else None

        resumen.append({
            'alumno': a,
            'presente': presente,
            'ausente': ausente,
            'retardo': retardo,
            'justificado': justificado,
            'total': total,
            'porcentaje': porcentaje,
        })

        config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_asistencias_grupo.html', {
        'grupo': grupo,
        'materia_sel': materia_sel,
        'fecha_inicio': fecha_inicio_str or '',
        'fecha_fin': fecha_fin_str or '',
        'resumen': resumen,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="asistencias_{grupo.nombre}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


# ============================================================
#  Incidencias
# ============================================================

@login_required
@requiere_permiso('incidencias', 'ver')
def incidencias_lista(request):
    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    incidencias = Incidencia.objects.select_related(
        'alumno', 'grupo_materia__grupo', 'grupo_materia__materia', 'reportado_por'
    )

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        incidencias = incidencias.filter(grupo_materia__profesor=profesor)

    grupo_id = request.GET.get('grupo')
    materia_id = request.GET.get('materia')
    tipo = request.GET.get('tipo')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    if grupo_id:
        incidencias = incidencias.filter(grupo_materia__grupo_id=grupo_id)
    if materia_id:
        incidencias = incidencias.filter(grupo_materia__materia_id=materia_id)
    if tipo:
        incidencias = incidencias.filter(tipo_reporte=tipo)
    if fecha_inicio_str:
        try:
            incidencias = incidencias.filter(
                fecha__gte=datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            )
        except ValueError:
            pass
    if fecha_fin_str:
        try:
            incidencias = incidencias.filter(
                fecha__lte=datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    incidencias = incidencias.order_by('-fecha')[:200]

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
        materias = Materia.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
    else:
        grupos = Grupo.objects.all().order_by('nombre')
        materias = Materia.objects.all().order_by('nombre')

    return render(request, 'horarios/incidencias_lista.html', {
        'incidencias': incidencias,
        'grupos': grupos,
        'materias': materias,
        'tipos': Incidencia.TIPOS,
        'grupo_sel': grupo_id or '',
        'materia_sel': materia_id or '',
        'tipo_sel': tipo or '',
        'fecha_inicio': fecha_inicio_str or '',
        'fecha_fin': fecha_fin_str or '',
        'es_coordinador': es_coordinador,
    })


@login_required
@requiere_permiso('incidencias', 'editar')
def incidencia_crear(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Solo los profesores pueden crear incidencias.')
        return redirect('horarios:incidencias_lista')

    profesor = request.user.perfil.profesor

    gms = GrupoMateria.objects.filter(profesor=profesor).select_related('grupo', 'materia')
    grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')

    if request.method == 'POST':
        form = IncidenciaForm(request.POST)
        if form.is_valid():
            incidencia = form.save(commit=False)
            incidencia.reportado_por = request.user
            incidencia.save()
            messages.success(request, 'Incidencia registrada.')
            return redirect('horarios:incidencias_lista')
        else:
            messages.error(request, 'Formulario inválido.')
    else:
        form = IncidenciaForm()

    return render(request, 'horarios/incidencia_form.html', {
        'form': form,
        'grupos': grupos,
        'gms': gms,
        'tipos': Incidencia.TIPOS,
        'accion': 'crear',
        'hoy': date.today().isoformat(),
    })


@login_required
@requiere_permiso('incidencias', 'editar')
def incidencia_editar(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, pk=incidencia_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and incidencia.grupo_materia.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para editar esta incidencia.')
        return redirect('horarios:incidencias_lista')

    if request.method == 'POST':
        form = IncidenciaForm(request.POST, instance=incidencia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Incidencia actualizada.')
            return redirect('horarios:incidencias_lista')
        else:
            messages.error(request, 'Formulario inválido.')
    else:
        form = IncidenciaForm(instance=incidencia)

    return render(request, 'horarios/incidencia_form.html', {
        'form': form,
        'tipos': Incidencia.TIPOS,
        'accion': 'editar',
        'incidencia': incidencia,
    })


@login_required
@requiere_permiso('incidencias', 'editar')
def incidencia_eliminar(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, pk=incidencia_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and incidencia.grupo_materia.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para eliminar esta incidencia.')
        return redirect('horarios:incidencias_lista')

    if request.method == 'POST':
        incidencia.delete()
        messages.success(request, 'Incidencia eliminada.')
        return redirect('horarios:incidencias_lista')

    return render(request, 'horarios/incidencia_confirmar_eliminar.html', {
        'incidencia': incidencia,
    })


@login_required
def alumnos_por_gm(request):
    gm_id = request.GET.get('gm')

    if not gm_id:
        return JsonResponse({'alumnos': []})

    try:
        gm = GrupoMateria.objects.get(pk=gm_id)
    except GrupoMateria.DoesNotExist:
        return JsonResponse({'alumnos': []})

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_gm = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and gm.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_profesor_del_gm):
        return JsonResponse({'alumnos': []})

    alumnos = Alumno.objects.filter(
        grupo=gm.grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    data = [
        {
            'id': a.id,
            'nombre': f"{a.apellido_paterno} {a.apellido_materno or ''} {a.nombre}".strip(),
            'matricula': a.matricula,
        }
        for a in alumnos
    ]

    return JsonResponse({'alumnos': data})


# ============================================================
#  Bitácora de desempeño
# ============================================================

def _calcular_total_desempeno(subtotal):
    """
    Regla de redondeo por bloques:
    - 50-54 → 50
    - 55-59 → 50 (reprobatorio)
    - 60-64 → 60
    - 65-69 → 70
    - 70-74 → 70
    - 75-79 → 80
    - 80-84 → 80
    - 85-89 → 90
    - 90-94 → 90
    - 95-99 → 100
    - 100 → 100
    """
    subtotal = int(subtotal)
    if 55 <= subtotal <= 59:
        return 50
    if subtotal >= 100:
        return 100
    decena = (subtotal // 10) * 10
    if subtotal % 10 < 5:
        return decena
    else:
        return min(decena + 10, 100)


@login_required
@requiere_permiso('desempeno', 'ver')
def desempeno_seleccionar(request):
    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
    else:
        grupos = Grupo.objects.all().order_by('nombre')

    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')

    if request.method == 'POST':
        grupo_id = request.POST.get('grupo')
        materia_id = request.POST.get('materia')
        periodo_id = request.POST.get('periodo')

        if grupo_id and materia_id and periodo_id:
            return redirect(
                f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': grupo_id})}"
                f"?materia={materia_id}&periodo={periodo_id}"
            )

        messages.error(request, 'Debes seleccionar grupo, materia y periodo.')

    return render(request, 'horarios/desempeno_seleccionar.html', {
        'grupos': grupos,
        'periodos': periodos,
    })


@login_required
@requiere_permiso('desempeno', 'ver')
def desempeno_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        if not GrupoMateria.objects.filter(grupo=grupo, profesor=profesor).exists():
            messages.error(request, 'No impartes clases en este grupo.')
            return redirect('horarios:desempeno_seleccionar')

    materia_id = request.GET.get('materia')
    periodo_id = request.GET.get('periodo')

    gm = None
    if materia_id:
        if es_profesor and not es_coordinador:
            profesor = request.user.perfil.profesor
            gm = GrupoMateria.objects.filter(
                grupo=grupo,
                materia_id=materia_id,
                profesor=profesor
            ).first()
        else:
            gm = GrupoMateria.objects.filter(
                grupo=grupo,
                materia_id=materia_id
            ).first()

    periodo = None
    if periodo_id:
        try:
            periodo = Periodo.objects.get(pk=periodo_id)
        except Periodo.DoesNotExist:
            periodo = None

    if not gm or not periodo:
        if es_profesor and not es_coordinador:
            profesor = request.user.perfil.profesor
            gm = GrupoMateria.objects.filter(grupo=grupo, profesor=profesor).first()
        else:
            gm = GrupoMateria.objects.filter(grupo=grupo).first()

        if not periodo:
            periodo = Periodo.objects.filter(activo=True).order_by('-fecha_inicio').first()

    if not gm or not periodo:
        messages.warning(request, 'No hay materia o periodo disponibles.')
        return redirect('horarios:desempeno_seleccionar')

    # Materias para el selector
    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo,
            grupomateria__profesor=profesor
        ).distinct().order_by('nombre')
    else:
        materias = Materia.objects.filter(
            grupomateria__grupo=grupo
        ).distinct().order_by('nombre')

    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')

    evidencias = EvidenciaDesempeno.objects.filter(
        grupo_materia=gm, periodo=periodo
    ).order_by('fecha', 'nombre')

    suma_porcentajes = sum(float(e.porcentaje) for e in evidencias)

    alumnos = alumnos_para_grupo_materia(gm)

    calificaciones = {}
    for c in CalificacionEvidencia.objects.filter(
        evidencia__in=evidencias
    ):
        calificaciones[(c.alumno_id, c.evidencia_id)] = c

    filas = []
    for a in alumnos:
        cals = []
        suma_obtenida = 0
        porcentaje_total = 0

        for e in evidencias:
            ce = calificaciones.get((a.id, e.id))
            cals.append(ce)
            if ce and ce.porcentaje_obtenido is not None:
                suma_obtenida += float(ce.porcentaje_obtenido)
                porcentaje_total += float(e.porcentaje)

        subtotal = round(suma_obtenida, 2)
        total = _calcular_total_desempeno(subtotal)
        calificacion_boleta = round(total / 10, 2)

        filas.append({
            'alumno': a,
            'calificaciones': cals,
            'suma_obtenida': suma_obtenida,
            'subtotal': subtotal,
            'total': total,
            'calificacion_boleta': calificacion_boleta,
            'porcentaje_total': porcentaje_total,
        })

    return render(request, 'horarios/desempeno_grupo.html', {
        'grupo': grupo,
        'gm': gm,
        'gms': GrupoMateria.objects.filter(grupo=grupo).select_related('materia') if es_coordinador else GrupoMateria.objects.filter(grupo=grupo, profesor=request.user.perfil.profesor).select_related('materia'),
        'materias': materias,
        'periodo': periodo,
        'periodos': periodos,
        'evidencias': evidencias,
        'filas': filas,
        'suma_porcentajes': suma_porcentajes,
    })


@login_required
@requiere_permiso('desempeno', 'editar')
def evidencia_crear(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

        # Validación: si es profesor, solo puede crear evidencias en sus grupos.
    # Si es auxiliar con permiso 'desempeno.editar', puede crear en cualquier grupo.
    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    gm_id = request.GET.get('materia') or request.POST.get('grupo_materia')
    periodo_id = request.GET.get('periodo') or request.POST.get('periodo')

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        gms = GrupoMateria.objects.filter(grupo=grupo, profesor=profesor).select_related('materia')
    else:
        gms = GrupoMateria.objects.filter(grupo=grupo).select_related('materia')

    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')

    if request.method == 'POST':
        gm_id = request.POST.get('grupo_materia')
        periodo_id = request.POST.get('periodo')
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', 'tarea')
        porcentaje = request.POST.get('porcentaje')
        fecha_str = request.POST.get('fecha')
        descripcion = request.POST.get('descripcion', '').strip()

        if not (gm_id and periodo_id and nombre and porcentaje and fecha_str):
            messages.error(request, 'Todos los campos son obligatorios.')
        else:
            try:
                if es_profesor and not es_coordinador:
                    gm = GrupoMateria.objects.get(
                        pk=gm_id,
                        profesor=request.user.perfil.profesor,
                        grupo=grupo
                    )
                else:
                    gm = GrupoMateria.objects.get(pk=gm_id, grupo=grupo)
                periodo = Periodo.objects.get(pk=periodo_id)
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

                EvidenciaDesempeno.objects.create(
                    grupo_materia=gm,
                    periodo=periodo,
                    nombre=nombre,
                    tipo=tipo,
                    porcentaje=Decimal(porcentaje.replace(',', '.')),
                    fecha=fecha,
                    descripcion=descripcion or None,
                    creada_por=request.user,
                )
                messages.success(request, 'Evidencia creada.')
                return redirect(
                    f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': grupo.id})}"
                    f"?materia={gm_id}&periodo={periodo_id}"
                )
            except (GrupoMateria.DoesNotExist, Periodo.DoesNotExist, ValueError, InvalidOperation):
                messages.error(request, 'Datos inválidos.')

    return render(request, 'horarios/evidencia_form.html', {
        'grupo': grupo,
        'gms': gms,
        'periodos': periodos,
        'tipos': EvidenciaDesempeno.TIPOS,
        'gm_sel': gm_id or '',
        'periodo_sel': periodo_id or '',
        'accion': 'crear',
        'hoy': date.today().isoformat(),
    })


@login_required
@requiere_permiso('desempeno', 'editar')
def evidencia_editar(request, evidencia_id):
    evidencia = get_object_or_404(EvidenciaDesempeno, pk=evidencia_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and evidencia.grupo_materia.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para editar esta evidencia.')
        return redirect('horarios:desempeno_seleccionar')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', 'tarea')
        porcentaje = request.POST.get('porcentaje')
        fecha_str = request.POST.get('fecha')
        descripcion = request.POST.get('descripcion', '').strip()

        if not (nombre and porcentaje and fecha_str):
            messages.error(request, 'Todos los campos son obligatorios.')
        else:
            try:
                evidencia.nombre = nombre
                evidencia.tipo = tipo
                evidencia.porcentaje = Decimal(porcentaje.replace(',', '.'))
                evidencia.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                evidencia.descripcion = descripcion or None
                evidencia.save()
                messages.success(request, 'Evidencia actualizada.')
                return redirect(
                    f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': evidencia.grupo_materia.grupo.id})}"
                    f"?materia={evidencia.grupo_materia.id}&periodo={evidencia.periodo.id}"
                )
            except (ValueError, InvalidOperation):
                messages.error(request, 'Datos inválidos.')

    return render(request, 'horarios/evidencia_form.html', {
        'evidencia': evidencia,
        'tipos': EvidenciaDesempeno.TIPOS,
        'accion': 'editar',
    })


@login_required
@requiere_permiso('desempeno', 'editar')
def evidencia_eliminar(request, evidencia_id):
    evidencia = get_object_or_404(EvidenciaDesempeno, pk=evidencia_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and evidencia.grupo_materia.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para eliminar esta evidencia.')
        return redirect('horarios:desempeno_seleccionar')

    if request.method == 'POST':
        gm_id = evidencia.grupo_materia.id
        periodo_id = evidencia.periodo.id
        grupo_id = evidencia.grupo_materia.grupo.id
        evidencia.delete()
        messages.success(request, 'Evidencia eliminada.')
        return redirect(
            f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': grupo_id})}"
            f"?materia={gm_id}&periodo={periodo_id}"
        )

    return render(request, 'horarios/evidencia_confirmar_eliminar.html', {
        'evidencia': evidencia,
    })


@login_required
@requiere_permiso('desempeno', 'editar')
def capturar_desempeno(request, evidencia_id):
    evidencia = get_object_or_404(EvidenciaDesempeno, pk=evidencia_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and evidencia.grupo_materia.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:desempeno_seleccionar')

    gm = evidencia.grupo_materia
    alumnos = Alumno.objects.filter(
        grupo=gm.grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    if request.method == 'POST':
        for alumno in alumnos:
            porcentaje = request.POST.get(f'porcentaje_{alumno.id}', '').strip()
            obs = request.POST.get(f'obs_{alumno.id}', '').strip()

            if porcentaje:
                try:
                    porcentaje_obtenido = Decimal(porcentaje.replace(',', '.'))
                    CalificacionEvidencia.objects.update_or_create(
                        evidencia=evidencia,
                        alumno=alumno,
                        defaults={
                            'porcentaje_obtenido': porcentaje_obtenido,
                            'observaciones': obs or None,
                            'capturada_por': request.user,
                        }
                    )
                except InvalidOperation:
                    continue
            else:
                CalificacionEvidencia.objects.filter(
                    evidencia=evidencia, alumno=alumno
                ).delete()

        messages.success(request, 'Calificaciones guardadas.')
        return redirect(
            f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': gm.grupo.id})}"
            f"?materia={gm.id}&periodo={evidencia.periodo.id}"
        )

    calificaciones = {
        c.alumno_id: c
        for c in CalificacionEvidencia.objects.filter(evidencia=evidencia)
    }

    alumnos_con_calif = [(a, calificaciones.get(a.id)) for a in alumnos]

    return render(request, 'horarios/capturar_desempeno.html', {
        'evidencia': evidencia,
        'gm': gm,
        'alumnos_con_calif': alumnos_con_calif,
    })


@login_required
@requiere_permiso('desempeno', 'editar')
def mandar_desempeno_a_boleta(request, alumno_id, gm_id, periodo_id):
    """Calcula el total del desempeño y lo guarda como Calificacion (0-10)."""
    if request.method != 'POST':
        return redirect('horarios:desempeno_seleccionar')

    alumno = get_object_or_404(Alumno, pk=alumno_id)
    gm = get_object_or_404(GrupoMateria, pk=gm_id)
    periodo = get_object_or_404(Periodo, pk=periodo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_gm = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and gm.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_profesor_del_gm):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:desempeno_seleccionar')

    evidencias = EvidenciaDesempeno.objects.filter(
        grupo_materia=gm, periodo=periodo
    )

    subtotal = 0.0
    for e in evidencias:
        ce = CalificacionEvidencia.objects.filter(
            evidencia=e, alumno=alumno
        ).first()
        if ce and ce.porcentaje_obtenido is not None:
            subtotal += float(ce.porcentaje_obtenido)

    total = _calcular_total_desempeno(int(subtotal))
    calificacion_boleta = Decimal(str(total / 10)).quantize(Decimal('0.01'))

    Calificacion.objects.update_or_create(
        alumno=alumno,
        grupo_materia=gm,
        periodo=periodo,
        defaults={
            'calificacion': calificacion_boleta,
            'capturada_por': request.user,
            'observaciones': f'Desde bitácora de desempeño (subtotal: {subtotal}%, total: {total}%)',
        }
    )

    messages.success(
        request,
        f'Calificación {calificacion_boleta} enviada a la boleta de {alumno.nombre_completo()}.'
    )
    return redirect(
        f"{reverse('horarios:desempeno_grupo', kwargs={'grupo_id': gm.grupo.id})}"
        f"?materia={gm.id}&periodo={periodo.id}"
    )


# ============================================================
#  Planeaciones
# ============================================================

@login_required
@requiere_permiso('planeaciones', 'ver')
def planeaciones_lista(request):
    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not (es_profesor or es_coordinador):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:dashboard')

    planeaciones = Planeacion.objects.select_related(
        'profesor', 'grupo_materia__grupo', 'grupo_materia__materia', 'periodo'
    )

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        planeaciones = planeaciones.filter(profesor=profesor)

    grupo_id = request.GET.get('grupo')
    materia_id = request.GET.get('materia')
    periodo_id = request.GET.get('periodo')
    estado = request.GET.get('estado')

    if grupo_id:
        planeaciones = planeaciones.filter(grupo_materia__grupo_id=grupo_id)
    if materia_id:
        planeaciones = planeaciones.filter(grupo_materia__materia_id=materia_id)
    if periodo_id:
        planeaciones = planeaciones.filter(periodo_id=periodo_id)
    if estado:
        planeaciones = planeaciones.filter(estado=estado)

    planeaciones = planeaciones.order_by('-fecha_inicio')

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        grupos = Grupo.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
        materias = Materia.objects.filter(grupomateria__profesor=profesor).distinct().order_by('nombre')
    else:
        grupos = Grupo.objects.all().order_by('nombre')
        materias = Materia.objects.all().order_by('nombre')

    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')

    return render(request, 'horarios/planeaciones_lista.html', {
        'planeaciones': planeaciones,
        'grupos': grupos,
        'materias': materias,
        'periodos': periodos,
        'estados': Planeacion.ESTADOS,
        'grupo_sel': grupo_id or '',
        'materia_sel': materia_id or '',
        'periodo_sel': periodo_id or '',
        'estado_sel': estado or '',
        'es_coordinador': es_coordinador,
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def planeacion_crear(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.profesor:
        messages.error(request, 'Solo los profesores pueden crear planeaciones.')
        return redirect('horarios:planeaciones_lista')

    profesor = request.user.perfil.profesor
    gms = GrupoMateria.objects.filter(profesor=profesor).select_related('grupo', 'materia')
    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')

    if request.method == 'POST':
        gm_id = request.POST.get('grupo_materia')
        periodo_id = request.POST.get('periodo')
        titulo = request.POST.get('titulo', '').strip()
        tema = request.POST.get('tema', '').strip()
        objetivo = request.POST.get('objetivo', '').strip()
        fecha_inicio_str = request.POST.get('fecha_inicio')
        fecha_fin_str = request.POST.get('fecha_fin')
        estado = request.POST.get('estado', 'borrador')
        observaciones = request.POST.get('observaciones', '').strip()

        if not (gm_id and periodo_id and titulo and tema and objetivo and fecha_inicio_str and fecha_fin_str):
            messages.error(request, 'Todos los campos obligatorios deben estar llenos.')
        else:
            try:
                gm = GrupoMateria.objects.get(pk=gm_id, profesor=profesor)
                periodo = Periodo.objects.get(pk=periodo_id)
                fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()

                if fecha_fin < fecha_inicio:
                    messages.error(request, 'La fecha fin no puede ser anterior a la fecha inicio.')
                else:
                    plan = Planeacion.objects.create(
                        profesor=profesor,
                        grupo_materia=gm,
                        periodo=periodo,
                        titulo=titulo,
                        tema=tema,
                        objetivo=objetivo,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin,
                        estado=estado,
                        observaciones=observaciones or None,
                        creada_por=request.user,
                    )
                    messages.success(request, 'Planeación creada. Ahora agrega las sesiones.')
                    return redirect('horarios:planeacion_editar', planeacion_id=plan.id)
            except (GrupoMateria.DoesNotExist, Periodo.DoesNotExist, ValueError):
                messages.error(request, 'Datos inválidos.')

    return render(request, 'horarios/planeacion_form.html', {
        'gms': gms,
        'periodos': periodos,
        'estados': Planeacion.ESTADOS,
        'accion': 'crear',
        'hoy': date.today().isoformat(),
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def planeacion_editar(request, planeacion_id):
    plan = get_object_or_404(Planeacion, pk=planeacion_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and plan.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para editar esta planeación.')
        return redirect('horarios:planeaciones_lista')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        tema = request.POST.get('tema', '').strip()
        objetivo = request.POST.get('objetivo', '').strip()
        fecha_inicio_str = request.POST.get('fecha_inicio')
        fecha_fin_str = request.POST.get('fecha_fin')
        estado = request.POST.get('estado', 'borrador')
        observaciones = request.POST.get('observaciones', '').strip()

        if not (titulo and tema and objetivo and fecha_inicio_str and fecha_fin_str):
            messages.error(request, 'Todos los campos obligatorios deben estar llenos.')
        else:
            try:
                plan.titulo = titulo
                plan.tema = tema
                plan.objetivo = objetivo
                plan.fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                plan.fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                plan.estado = estado
                plan.observaciones = observaciones or None
                plan.save()
                messages.success(request, 'Planeación actualizada.')
                return redirect('horarios:planeacion_editar', planeacion_id=plan.id)
            except ValueError:
                messages.error(request, 'Fecha inválida.')

    sesiones = plan.sesiones.all().order_by('numero')

    return render(request, 'horarios/planeacion_form.html', {
        'plan': plan,
        'sesiones': sesiones,
        'estados': Planeacion.ESTADOS,
        'accion': 'editar',
    })


@login_required
@requiere_permiso('planeaciones', 'ver')
def planeacion_ver(request, planeacion_id):
    plan = get_object_or_404(Planeacion, pk=planeacion_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and plan.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para ver esta planeación.')
        return redirect('horarios:planeaciones_lista')

    sesiones = plan.sesiones.all().order_by('numero')

    return render(request, 'horarios/planeacion_ver.html', {
        'plan': plan,
        'sesiones': sesiones,
        'es_coordinador': es_coordinador,
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def planeacion_eliminar(request, planeacion_id):
    plan = get_object_or_404(Planeacion, pk=planeacion_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and plan.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso para eliminar esta planeación.')
        return redirect('horarios:planeaciones_lista')

    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Planeación eliminada.')
        return redirect('horarios:planeaciones_lista')

    return render(request, 'horarios/planeacion_confirmar_eliminar.html', {
        'plan': plan,
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def sesion_crear(request, planeacion_id):
    plan = get_object_or_404(Planeacion, pk=planeacion_id)

    if not (hasattr(request.user, 'perfil') and request.user.perfil.profesor
            and plan.profesor == request.user.perfil.profesor):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:planeaciones_lista')

    siguiente_num = (plan.sesiones.order_by('-numero').first().numero + 1) if plan.sesiones.exists() else 1

    if request.method == 'POST':
        numero = request.POST.get('numero') or siguiente_num
        fecha_str = request.POST.get('fecha')
        duracion = request.POST.get('duracion_minutos', 50)
        recursos = request.POST.get('recursos', '').strip()
        producto = request.POST.get('producto', '').strip()
        actividades = request.POST.get('actividades', '').strip()

        if not (fecha_str and recursos and producto):
            messages.error(request, 'Fecha, recursos y producto son obligatorios.')
        else:
            try:
                SesionPlaneacion.objects.create(
                    planeacion=plan,
                    numero=int(numero),
                    fecha=datetime.strptime(fecha_str, '%Y-%m-%d').date(),
                    duracion_minutos=int(duracion),
                    recursos=recursos,
                    producto=producto,
                    actividades=actividades or None,
                )
                messages.success(request, 'Sesión agregada.')
                return redirect('horarios:planeacion_editar', planeacion_id=plan.id)
            except (ValueError, IntegrityError):
                messages.error(request, 'Datos inválidos o número de sesión duplicado.')

    return render(request, 'horarios/sesion_form.html', {
        'plan': plan,
        'siguiente_num': siguiente_num,
        'accion': 'crear',
        'hoy': date.today().isoformat(),
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def sesion_editar(request, sesion_id):
    sesion = get_object_or_404(SesionPlaneacion, pk=sesion_id)
    plan = sesion.planeacion

    if not (hasattr(request.user, 'perfil') and request.user.perfil.profesor
            and plan.profesor == request.user.perfil.profesor):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:planeaciones_lista')

    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        duracion = request.POST.get('duracion_minutos', 50)
        recursos = request.POST.get('recursos', '').strip()
        producto = request.POST.get('producto', '').strip()
        actividades = request.POST.get('actividades', '').strip()

        if not (fecha_str and recursos and producto):
            messages.error(request, 'Fecha, recursos y producto son obligatorios.')
        else:
            try:
                sesion.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                sesion.duracion_minutos = int(duracion)
                sesion.recursos = recursos
                sesion.producto = producto
                sesion.actividades = actividades or None
                sesion.save()
                messages.success(request, 'Sesión actualizada.')
                return redirect('horarios:planeacion_editar', planeacion_id=plan.id)
            except ValueError:
                messages.error(request, 'Datos inválidos.')

    return render(request, 'horarios/sesion_form.html', {
        'sesion': sesion,
        'plan': plan,
        'accion': 'editar',
    })


@login_required
@requiere_permiso('planeaciones', 'editar')
def sesion_eliminar(request, sesion_id):
    sesion = get_object_or_404(SesionPlaneacion, pk=sesion_id)
    plan = sesion.planeacion

    if not (hasattr(request.user, 'perfil') and request.user.perfil.profesor
            and plan.profesor == request.user.perfil.profesor):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:planeaciones_lista')

    if request.method == 'POST':
        sesion.delete()
        messages.success(request, 'Sesión eliminada.')
        return redirect('horarios:planeacion_editar', planeacion_id=plan.id)

    return render(request, 'horarios/sesion_confirmar_eliminar.html', {
        'sesion': sesion,
        'plan': plan,
    })


@login_required
@requiere_permiso('planeaciones', 'ver')
def pdf_planeacion(request, planeacion_id):
    plan = get_object_or_404(Planeacion, pk=planeacion_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_propietario = (
        hasattr(request.user, 'perfil')
        and request.user.perfil.profesor
        and plan.profesor == request.user.perfil.profesor
    )

    if not (es_coordinador or es_propietario):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:planeaciones_lista')

    sesiones = plan.sesiones.all().order_by('numero')

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_planeacion.html', {
        'plan': plan,
        'sesiones': sesiones,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="planeacion_{plan.id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


@login_required
@requiere_permiso('reportes', 'ver')
def reportes(request):
    """
    Dashboard de reportes con estadísticas y gráficos.
    Solo para coordinadores/staff.
    """
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    # Periodo seleccionado (el más reciente activo por defecto)
    periodos = Periodo.objects.filter(activo=True).order_by('-fecha_inicio')
    periodo_id = request.GET.get('periodo')
    periodo_sel = None

    if periodo_id:
        try:
            periodo_sel = Periodo.objects.get(pk=periodo_id)
        except Periodo.DoesNotExist:
            periodo_sel = None

    if not periodo_sel and periodos.exists():
        periodo_sel = periodos.first()

    # 1. Promedio por materia
    promedios_materia = []
    for m in Materia.objects.all().order_by('nombre'):
        califs = Calificacion.objects.filter(
            grupo_materia__materia=m,
            calificacion__isnull=False,
        )
        if periodo_sel:
            califs = califs.filter(periodo=periodo_sel)
        if califs.exists():
            suma = sum(float(c.calificacion) for c in califs)
            promedio = suma / califs.count()
            promedios_materia.append({
                'nombre': m.nombre,
                'promedio': round(promedio, 2),
            })

    # 2. Promedio por grupo
    promedios_grupo = []
    for g in Grupo.objects.all().order_by('nombre'):
        califs = Calificacion.objects.filter(
            alumno__grupo=g,
            calificacion__isnull=False,
        )
        if periodo_sel:
            califs = califs.filter(periodo=periodo_sel)
        if califs.exists():
            suma = sum(float(c.calificacion) for c in califs)
            promedio = suma / califs.count()
            promedios_grupo.append({
                'nombre': g.nombre,
                'promedio': round(promedio, 2),
            })

    # 3. Distribución de calificaciones
    califs_todas = Calificacion.objects.filter(calificacion__isnull=False)
    if periodo_sel:
        califs_todas = califs_todas.filter(periodo=periodo_sel)

    excelente = califs_todas.filter(calificacion__gte=9).count()
    bien = califs_todas.filter(calificacion__gte=7, calificacion__lt=9).count()
    regular = califs_todas.filter(calificacion__gte=6, calificacion__lt=7).count()
    reprobado = califs_todas.filter(calificacion__lt=6).count()

    distribucion = {
        'excelente': excelente,
        'bien': bien,
        'regular': regular,
        'reprobado': reprobado,
    }

    # 4. Asistencia por grupo
    asistencia_grupos = []
    for g in Grupo.objects.all().order_by('nombre'):
        asists = Asistencia.objects.filter(alumno__grupo=g)
        if periodo_sel:
            asists = asists.filter(fecha__range=[periodo_sel.fecha_inicio, periodo_sel.fecha_fin])
        if asists.exists():
            asistencia_grupos.append({
                'nombre': g.nombre,
                'presente': asists.filter(estado='presente').count(),
                'ausente': asists.filter(estado='ausente').count(),
                'retardo': asists.filter(estado='retardo').count(),
                'justificado': asists.filter(estado='justificado').count(),
            })

    # 5. Alumnos en riesgo (promedio < 6 o asistencia < 80%)
    alumnos_riesgo = []
    for a in Alumno.objects.filter(activo=True).select_related('grupo'):
        califs = Calificacion.objects.filter(alumno=a, calificacion__isnull=False)
        if periodo_sel:
            califs = califs.filter(periodo=periodo_sel)
        promedio = None
        if califs.exists():
            promedio = sum(float(c.calificacion) for c in califs) / califs.count()

        asists = Asistencia.objects.filter(alumno=a)
        if periodo_sel:
            asists = asists.filter(fecha__range=[periodo_sel.fecha_inicio, periodo_sel.fecha_fin])
        total_asist = asists.count()
        asistio = asists.filter(estado__in=['presente', 'retardo', 'justificado']).count()
        porcentaje_asist = (asistio / total_asist * 100) if total_asist > 0 else None

        en_riesgo = (
            (promedio is not None and promedio < 6) or
            (porcentaje_asist is not None and porcentaje_asist < 80)
        )

        if en_riesgo:
            alumnos_riesgo.append({
                'alumno': a,
                'promedio': round(promedio, 2) if promedio is not None else None,
                'porcentaje_asist': round(porcentaje_asist, 1) if porcentaje_asist is not None else None,
            })

    # 6. Carga docente
    carga_docente = []
    for p in Profesor.objects.filter(activo=True).order_by('nombre'):
        total_horas = Asignacion.objects.filter(profesor=p).count()
        if total_horas > 0:
            carga_docente.append({
                'nombre': p.nombre,
                'horas': total_horas,
            })

    return render(request, 'horarios/reportes.html', {
        'periodos': periodos,
        'periodo_sel': periodo_sel,
        'promedios_materia': promedios_materia,
        'promedios_grupo': promedios_grupo,
        'distribucion': distribucion,
        'asistencia_grupos': asistencia_grupos,
        'alumnos_riesgo': alumnos_riesgo,
        'carga_docente': carga_docente,
    })


@login_required
@requiere_permiso('lista_asistencia', 'ver')
def pdf_lista_asistencia(request, grupo_id):
    """
    Genera un PDF con la lista de asistencia imprimible del grupo.
    Solo incluye días hábiles (lunes a viernes).
    Divide el mes en dos quincenas.
    """
    import calendar

    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=grupo, profesor=profesor
        ).exists()

    

    hoy = date.today()
    try:
        mes = int(request.GET.get('mes', hoy.month))
        if mes < 1 or mes > 12:
            mes = hoy.month
    except (ValueError, TypeError):
        mes = hoy.month

    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (ValueError, TypeError):
        anio = hoy.year

    num_dias = calendar.monthrange(anio, mes)[1]

    dias_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # Construir lista SOLO con días hábiles (lunes a viernes)
    dias_info = []
    for d in range(1, num_dias + 1):
        fecha_dia = date(anio, mes, d)
        if fecha_dia.weekday() < 5:  # 0=Lun ... 4=Vie
            nombre_dia = dias_semana[fecha_dia.weekday()]
            dias_info.append((d, nombre_dia))

    # Dividir en dos mitades (no exactamente quincenas, sino por cantidad de días hábiles)
    mitad = (len(dias_info) + 1) // 2
    dias_primera = dias_info[:mitad]
    dias_segunda = dias_info[mitad:]

    alumnos = Alumno.objects.filter(
        grupo=grupo, activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    meses_es = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    nombre_mes = meses_es[mes]

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_lista_asistencia.html', {
        'grupo': grupo,
        'alumnos': alumnos,
        'mes': mes,
        'anio': anio,
        'num_dias': num_dias,
        'nombre_mes': nombre_mes,
        'dias_primera': dias_primera,
        'dias_segunda': dias_segunda,
        'total_dias_habiles': len(dias_info),
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="lista_asistencia_{grupo.nombre}_{mes}_{anio}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


@login_required
@requiere_permiso('desempeno', 'ver')
def desempeno_pendientes(request, grupo_id):
    """
    Muestra los alumnos del grupo que tienen evidencias sin capturar
    (porcentaje_obtenido es None o 0) para un grupo_materia y periodo.
    """
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_profesor = hasattr(request.user, 'perfil') and request.user.perfil.profesor
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    

    if es_profesor and not es_coordinador:
        profesor = request.user.perfil.profesor
        if not GrupoMateria.objects.filter(grupo=grupo, profesor=profesor).exists():
            messages.error(request, 'No impartes clases en este grupo.')
            return redirect('horarios:desempeno_seleccionar')

    gm_id = request.GET.get('materia')
    periodo_id = request.GET.get('periodo')

    gm = None
    if gm_id:
        try:
            gm = GrupoMateria.objects.get(pk=gm_id, grupo=grupo)
        except GrupoMateria.DoesNotExist:
            gm = None

    periodo = None
    if periodo_id:
        try:
            periodo = Periodo.objects.get(pk=periodo_id)
        except Periodo.DoesNotExist:
            periodo = None

    if not gm or not periodo:
        messages.warning(request, 'Selecciona una materia y un periodo.')
        return redirect('horarios:desempeno_seleccionar')

    # Evidencias del gm + periodo
    evidencias = EvidenciaDesempeno.objects.filter(
        grupo_materia=gm, periodo=periodo
    ).order_by('fecha', 'nombre')

    # Alumnos del grupo
        # Alumnos del grupo (respetando subgrupo del GrupoMateria)
    alumnos = alumnos_para_grupo_materia(gm)

    # Calificaciones existentes: {(alumno_id, evidencia_id): calificacion_obj}
    calificaciones = {}
    for c in CalificacionEvidencia.objects.filter(evidencia__in=evidencias):
        calificaciones[(c.alumno_id, c.evidencia_id)] = c

    # Construir lista de pendientes
    pendientes = []
    for a in alumnos:
        evidencias_faltantes = []
        for e in evidencias:
            ce = calificaciones.get((a.id, e.id))
            # Pendiente si no existe calificación, o es None, o es 0
            if ce is None or ce.porcentaje_obtenido is None or float(ce.porcentaje_obtenido) == 0:
                evidencias_faltantes.append({
                    'evidencia': e,
                    'fecha': e.fecha,
                    'porcentaje': e.porcentaje,
                })

        if evidencias_faltantes:
            pendientes.append({
                'alumno': a,
                'evidencias_faltantes': evidencias_faltantes,
                'num_faltantes': len(evidencias_faltantes),
            })

    # Ordenar por número de faltantes (de mayor a menor)
    pendientes.sort(key=lambda x: x['num_faltantes'], reverse=True)

    return render(request, 'horarios/desempeno_pendientes.html', {
        'grupo': grupo,
        'gm': gm,
        'periodo': periodo,
        'evidencias': evidencias,
        'pendientes': pendientes,
        'total_alumnos': alumnos.count(),
        'total_pendientes': len(pendientes),
    })

from datetime import timedelta

@login_required
@requiere_permiso('calendario', 'ver')
def calendario(request):
    """Vista mensual del calendario con eventos."""
    import calendar

    hoy = date.today()

    try:
        mes = int(request.GET.get('mes', hoy.month))
        if mes < 1 or mes > 12:
            mes = hoy.month
    except (ValueError, TypeError):
        mes = hoy.month

    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (ValueError, TypeError):
        anio = hoy.year

    if mes == 1:
        mes_anterior = 12
        anio_anterior = anio - 1
    else:
        mes_anterior = mes - 1
        anio_anterior = anio

    if mes == 12:
        mes_siguiente = 1
        anio_siguiente = anio + 1
    else:
        mes_siguiente = mes + 1
        anio_siguiente = anio

    primer_dia = date(anio, mes, 1)
    if mes == 12:
        ultimo_dia = date(anio, 12, 31)
    else:
        ultimo_dia = date(anio, mes + 1, 1) - timedelta(days=1)

    eventos = EventoCalendario.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia
    ).order_by('fecha', 'hora_inicio')

    eventos_por_dia = {}
    for ev in eventos:
        if ev.fecha not in eventos_por_dia:
            eventos_por_dia[ev.fecha] = []
        eventos_por_dia[ev.fecha].append(ev)

    cal = calendar.Calendar(firstweekday=0)
    semanas = []
    for semana in cal.monthdatescalendar(anio, mes):
        dias_semana = []
        for dia in semana:
            dias_semana.append({
                'fecha': dia,
                'dia': dia.day,
                'es_del_mes': dia.month == mes,
                'es_hoy': dia == hoy,
                'eventos': eventos_por_dia.get(dia, []),
            })
        semanas.append(dias_semana)

    meses_es = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    return render(request, 'horarios/calendario.html', {
        'mes': mes,
        'anio': anio,
        'nombre_mes': meses_es[mes],
        'mes_anterior': mes_anterior,
        'anio_anterior': anio_anterior,
        'mes_siguiente': mes_siguiente,
        'anio_siguiente': anio_siguiente,
        'semanas': semanas,
        'eventos': eventos,
        'tipos_con_color': [
    ('examen', 'Examen', '#e74c3c'),
    ('consejo', 'Consejo Técnico', '#f39c12'),
    ('evento', 'Evento escolar', '#3498db'),
    ('feriado', 'Día feriado', '#95a5a6'),
    ('reunion', 'Reunión', '#17a2b8'),
    ('suspension', 'Suspensión de clases', '#2c3e50'),
    ('otro', 'Otro', '#6c757d'),
],
    })

@login_required
@requiere_permiso('calendario', 'editar')
def evento_crear(request):
    """Crear un evento del calendario."""
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden crear eventos.')
        return redirect('horarios:calendario')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo = request.POST.get('tipo', 'evento')
        fecha_str = request.POST.get('fecha')
        fecha_fin_str = request.POST.get('fecha_fin') or None
        todo_el_dia = request.POST.get('todo_el_dia') == 'on'
        hora_inicio_str = request.POST.get('hora_inicio') or None
        hora_fin_str = request.POST.get('hora_fin') or None

        if not (titulo and fecha_str):
            messages.error(request, 'Título y fecha son obligatorios.')
        else:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                fecha_fin = None
                if fecha_fin_str:
                    fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()

                hora_inicio = None
                hora_fin = None
                if not todo_el_dia:
                    if hora_inicio_str:
                        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
                    if hora_fin_str:
                        hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()

                EventoCalendario.objects.create(
                    fecha=fecha,
                    fecha_fin=fecha_fin,
                    titulo=titulo,
                    descripcion=descripcion or None,
                    tipo=tipo,
                    todo_el_dia=todo_el_dia,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                    creado_por=request.user,
                )
                messages.success(request, 'Evento creado.')
                return redirect(f"{reverse('horarios:calendario')}?mes={fecha.month}&anio={fecha.year}")
            except ValueError:
                messages.error(request, 'Fecha u hora inválida.')

    fecha_default = request.GET.get('fecha') or date.today().isoformat()

    return render(request, 'horarios/evento_form.html', {
        'tipos': EventoCalendario.TIPOS,
        'accion': 'crear',
        'fecha_default': fecha_default,
    })

@login_required
@requiere_permiso('calendario', 'editar')
def evento_editar(request, evento_id):
    """Editar un evento."""
    evento = get_object_or_404(EventoCalendario, pk=evento_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:calendario')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo = request.POST.get('tipo', 'evento')
        fecha_str = request.POST.get('fecha')
        fecha_fin_str = request.POST.get('fecha_fin') or None
        todo_el_dia = request.POST.get('todo_el_dia') == 'on'
        hora_inicio_str = request.POST.get('hora_inicio') or None
        hora_fin_str = request.POST.get('hora_fin') or None

        if not (titulo and fecha_str):
            messages.error(request, 'Título y fecha son obligatorios.')
        else:
            try:
                evento.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                evento.fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else None
                evento.titulo = titulo
                evento.descripcion = descripcion or None
                evento.tipo = tipo
                evento.todo_el_dia = todo_el_dia
                evento.hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time() if hora_inicio_str and not todo_el_dia else None
                evento.hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time() if hora_fin_str and not todo_el_dia else None
                evento.save()
                messages.success(request, 'Evento actualizado.')
                return redirect(f"{reverse('horarios:calendario')}?mes={evento.fecha.month}&anio={evento.fecha.year}")
            except ValueError:
                messages.error(request, 'Fecha u hora inválida.')

    return render(request, 'horarios/evento_form.html', {
        'evento': evento,
        'tipos': EventoCalendario.TIPOS,
        'accion': 'editar',
    })

@login_required
@requiere_permiso('calendario', 'editar')
def evento_eliminar(request, evento_id):
    """Eliminar un evento."""
    evento = get_object_or_404(EventoCalendario, pk=evento_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:calendario')

    if request.method == 'POST':
        mes = evento.fecha.month
        anio = evento.fecha.year
        evento.delete()
        messages.success(request, 'Evento eliminado.')
        return redirect(f"{reverse('horarios:calendario')}?mes={mes}&anio={anio}")

    return render(request, 'horarios/evento_confirmar_eliminar.html', {
        'evento': evento,
    })

@login_required
@requiere_permiso('calendario', 'ver')
def pdf_calendario(request):
    """Genera PDF del calendario mensual."""
    import calendar

    hoy = date.today()

    try:
        mes = int(request.GET.get('mes', hoy.month))
        if mes < 1 or mes > 12:
            mes = hoy.month
    except (ValueError, TypeError):
        mes = hoy.month

    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (ValueError, TypeError):
        anio = hoy.year

    primer_dia = date(anio, mes, 1)
    if mes == 12:
        ultimo_dia = date(anio, 12, 31)
    else:
        ultimo_dia = date(anio, mes + 1, 1) - timedelta(days=1)

    eventos = EventoCalendario.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia
    ).order_by('fecha', 'hora_inicio')

    eventos_por_dia = {}
    for ev in eventos:
        if ev.fecha not in eventos_por_dia:
            eventos_por_dia[ev.fecha] = []
        eventos_por_dia[ev.fecha].append(ev)

    cal = calendar.Calendar(firstweekday=0)
    semanas = []
    for semana in cal.monthdatescalendar(anio, mes):
        dias_semana = []
        for dia in semana:
            dias_semana.append({
                'fecha': dia,
                'dia': dia.day,
                'es_del_mes': dia.month == mes,
                'eventos': eventos_por_dia.get(dia, []),
            })
        semanas.append(dias_semana)

    meses_es = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_calendario.html', {
        'mes': mes,
        'anio': anio,
        'nombre_mes': meses_es[mes],
        'semanas': semanas,
        'eventos': eventos,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="calendario_{mes}_{anio}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


from .models import ConfiguracionInstitucion

@login_required
@requiere_permiso('configuracion', 'ver')
def configuracion_institucion(request):
    """Editar la configuración de la institución."""
    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden editar la configuración.')
        return redirect('horarios:dashboard')

    config = ConfiguracionInstitucion.get_solo()

    if request.method == 'POST':
        config.nombre_institucion = request.POST.get('nombre_institucion', '').strip() or 'Mi Institución Educativa'
        config.direccion = request.POST.get('direccion', '').strip() or None
        config.telefono = request.POST.get('telefono', '').strip() or None
        config.email = request.POST.get('email', '').strip() or None
        config.sitio_web = request.POST.get('sitio_web', '').strip() or None
        config.ciclo_escolar = request.POST.get('ciclo_escolar', '').strip() or None
        config.lema = request.POST.get('lema', '').strip() or None
        config.director = request.POST.get('director', '').strip() or None

        if 'logo' in request.FILES:
            config.logo = request.FILES['logo']

        if request.POST.get('quitar_logo') == 'on':
            if config.logo:
                config.logo.delete(save=False)
            config.logo = None

        config.save()
        messages.success(request, 'Configuración actualizada.')
        return redirect('horarios:configuracion_institucion')

    return render(request, 'horarios/configuracion_institucion.html', {
        'config': config,
    })


@login_required
def alumno_crear(request, grupo_id):
    """Agregar un alumno nuevo a un grupo."""
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden agregar alumnos.')
        return redirect('horarios:lista_alumnos_grupo', grupo_id=grupo.id)

    if request.method == 'POST':
        matricula = request.POST.get('matricula', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        email = request.POST.get('email', '').strip()
        fecha_nacimiento_str = request.POST.get('fecha_nacimiento') or None

        if not (matricula and nombre and apellido_paterno):
            messages.error(request, 'Matrícula, nombre y apellido paterno son obligatorios.')
        else:
            if Alumno.objects.filter(matricula=matricula).exists():
                messages.error(request, f'Ya existe un alumno con la matrícula {matricula}.')
            else:
                try:
                    fecha_nacimiento = None
                    if fecha_nacimiento_str:
                        fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, '%Y-%m-%d').date()

                    Alumno.objects.create(
                        matricula=matricula,
                        nombre=nombre,
                        apellido_paterno=apellido_paterno,
                        apellido_materno=apellido_materno or None,
                        email=email or None,
                        grupo=grupo,
                        activo=True,
                        fecha_nacimiento=fecha_nacimiento,
                    )
                    messages.success(request, f'Alumno {nombre} {apellido_paterno} agregado al grupo {grupo.nombre}.')
                    return redirect('horarios:lista_alumnos_grupo', grupo_id=grupo.id)
                except ValueError:
                    messages.error(request, 'Fecha de nacimiento inválida.')

    return render(request, 'horarios/alumno_form.html', {
        'grupo': grupo,
        'accion': 'crear',
    })


@login_required
def alumno_editar(request, alumno_id):
    """Editar los datos de un alumno."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden editar alumnos.')
        if alumno.grupo:
            return redirect('horarios:lista_alumnos_grupo', grupo_id=alumno.grupo.id)
        return redirect('horarios:dashboard')

    if request.method == 'POST':
        matricula = request.POST.get('matricula', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        email = request.POST.get('email', '').strip()
        fecha_nacimiento_str = request.POST.get('fecha_nacimiento') or None
        activo = request.POST.get('activo') == 'on'

        if not (matricula and nombre and apellido_paterno):
            messages.error(request, 'Matrícula, nombre y apellido paterno son obligatorios.')
        else:
            if Alumno.objects.filter(matricula=matricula).exclude(pk=alumno.pk).exists():
                messages.error(request, f'Ya existe otro alumno con la matrícula {matricula}.')
            else:
                try:
                    alumno.matricula = matricula
                    alumno.nombre = nombre
                    alumno.apellido_paterno = apellido_paterno
                    alumno.apellido_materno = apellido_materno or None
                    alumno.email = email or None
                    alumno.activo = activo
                    if fecha_nacimiento_str:
                        alumno.fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, '%Y-%m-%d').date()
                    else:
                        alumno.fecha_nacimiento = None
                    alumno.save()
                    messages.success(request, 'Alumno actualizado.')
                    if alumno.grupo:
                        return redirect('horarios:lista_alumnos_grupo', grupo_id=alumno.grupo.id)
                    return redirect('horarios:dashboard')
                except ValueError:
                    messages.error(request, 'Fecha de nacimiento inválida.')

    return render(request, 'horarios/alumno_form.html', {
        'alumno': alumno,
        'grupo': alumno.grupo,
        'accion': 'editar',
    })


@login_required
def alumno_eliminar(request, alumno_id):
    """Eliminar un alumno."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)
    grupo_id = alumno.grupo.id if alumno.grupo else None

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden eliminar alumnos.')
        if grupo_id:
            return redirect('horarios:lista_alumnos_grupo', grupo_id=grupo_id)
        return redirect('horarios:dashboard')

    if request.method == 'POST':
        nombre = alumno.nombre_completo()
        alumno.delete()
        messages.success(request, f'Alumno {nombre} eliminado.')
        if grupo_id:
            return redirect('horarios:lista_alumnos_grupo', grupo_id=grupo_id)
        return redirect('horarios:dashboard')

    return render(request, 'horarios/alumno_confirmar_eliminar.html', {
        'alumno': alumno,
        'grupo': alumno.grupo,
    })


@login_required
def alumno_cambiar_grupo(request, alumno_id):
    """Cambiar a un alumno de grupo."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)
    grupo_original = alumno.grupo

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    if not es_coordinador:
        messages.error(request, 'Solo coordinadores pueden cambiar alumnos de grupo.')
        if grupo_original:
            return redirect('horarios:lista_alumnos_grupo', grupo_id=grupo_original.id)
        return redirect('horarios:dashboard')

    grupos = Grupo.objects.all().order_by('nombre')

    if request.method == 'POST':
        nuevo_grupo_id = request.POST.get('nuevo_grupo')
        if not nuevo_grupo_id:
            messages.error(request, 'Debes seleccionar un grupo.')
        else:
            try:
                nuevo_grupo = Grupo.objects.get(pk=nuevo_grupo_id)
                alumno.grupo = nuevo_grupo
                alumno.save()
                messages.success(request, f'Alumno {alumno.nombre_completo()} movido al grupo {nuevo_grupo.nombre}.')
                return redirect('horarios:lista_alumnos_grupo', grupo_id=nuevo_grupo.id)
            except Grupo.DoesNotExist:
                messages.error(request, 'Grupo no encontrado.')

    return render(request, 'horarios/alumno_cambiar_grupo.html', {
        'alumno': alumno,
        'grupo_original': grupo_original,
        'grupos': grupos,
    })


@login_required
def boleta_trimestral(request, alumno_id):
    """Muestra la boleta trimestral y final del alumno con fusión de materias paralelas."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=alumno.grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso para ver esta boleta.')
        return redirect('horarios:dashboard')

    anio_escolar = Periodo.objects.filter(tipo='anual', activo=True).order_by('-fecha_inicio').first()
    if not anio_escolar:
        anio_escolar = Periodo.objects.filter(tipo='anual').order_by('-fecha_inicio').first()

    if not anio_escolar:
        messages.warning(request, 'No hay un año escolar configurado.')
        return redirect('horarios:dashboard')

    trimestres = anio_escolar.hijos.filter(tipo='trimestre').order_by('fecha_inicio')

    # Agrupar materias paralelas
    materias_raw = Materia.objects.filter(
        grupomateria__grupo=alumno.grupo
    ).distinct().order_by('nombre')

    grupos_por_nombre = {}
    for m in materias_raw:
        nombre = m.nombre_boleta()
        if nombre not in grupos_por_nombre:
            grupos_por_nombre[nombre] = []
        grupos_por_nombre[nombre].append(m)

    materias_unicas = []
    for nombre_boleta, grupo_materias in sorted(grupos_por_nombre.items()):
        materias_unicas.append({
            'nombre': nombre_boleta,
            'materia_ids': [m.id for m in grupo_materias],
        })

    filas = []
    suma_final_materia = 0
    cuenta_final_materia = 0

    for mat in materias_unicas:
        promedios_trim = []
        suma_materia = 0
        cuenta_materia = 0

        for t in trimestres:
            periodos_eval = t.hijos.filter(tipo='periodo')
            califs = Calificacion.objects.filter(
                alumno=alumno,
                grupo_materia__materia_id__in=mat['materia_ids'],
                periodo__in=periodos_eval,
                calificacion__isnull=False,
            )
            if califs.exists():
                promedio = sum(float(c.calificacion) for c in califs) / califs.count()
                promedio_redondeado = _redondear_calificacion(promedio)
                promedios_trim.append(promedio_redondeado)
                suma_materia += promedio_redondeado
                cuenta_materia += 1
            else:
                promedios_trim.append(None)

        if cuenta_materia > 0:
            promedio_final = _redondear_calificacion(suma_materia / cuenta_materia)
            suma_final_materia += promedio_final
            cuenta_final_materia += 1
        else:
            promedio_final = None

        filas.append({
            'materia': mat['nombre'],
            'trimestres': promedios_trim,
            'promedio_final': promedio_final,
        })

    promedios_por_trimestre = []
    for i in range(len(trimestres)):
        suma = 0
        cuenta = 0
        for fila in filas:
            if fila['trimestres'][i] is not None:
                suma += fila['trimestres'][i]
                cuenta += 1
        promedios_por_trimestre.append(
            _redondear_calificacion(suma / cuenta) if cuenta > 0 else None
        )

    promedio_general_final = (
        _redondear_calificacion(suma_final_materia / cuenta_final_materia)
        if cuenta_final_materia > 0 else None
    )

    config_inst = ConfiguracionInstitucion.get_solo()

    return render(request, 'horarios/boleta_trimestral.html', {
        'alumno': alumno,
        'anio_escolar': anio_escolar,
        'trimestres': trimestres,
        'filas': filas,
        'promedios_por_trimestre': promedios_por_trimestre,
        'promedio_general_final': promedio_general_final,
        'config_institucion': config_inst,
    })

@login_required
def pdf_boleta_trimestral(request, alumno_id):
    """Genera PDF de la boleta trimestral con fusión de materias paralelas."""
    alumno = get_object_or_404(Alumno, pk=alumno_id)

    es_coordinador = (
        request.user.is_staff
        or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'coordinador')
    )

    es_profesor_del_grupo = False
    if hasattr(request.user, 'perfil') and request.user.perfil.profesor:
        profesor = request.user.perfil.profesor
        es_profesor_del_grupo = GrupoMateria.objects.filter(
            grupo=alumno.grupo, profesor=profesor
        ).exists()

    if not (es_coordinador or es_profesor_del_grupo):
        messages.error(request, 'No tienes permiso.')
        return redirect('horarios:dashboard')

    anio_escolar = Periodo.objects.filter(tipo='anual', activo=True).order_by('-fecha_inicio').first()
    if not anio_escolar:
        anio_escolar = Periodo.objects.filter(tipo='anual').order_by('-fecha_inicio').first()

    if not anio_escolar:
        messages.warning(request, 'No hay un año escolar configurado.')
        return redirect('horarios:dashboard')

    trimestres = anio_escolar.hijos.filter(tipo='trimestre').order_by('fecha_inicio')

    # Agrupar materias paralelas
    materias_raw = Materia.objects.filter(
        grupomateria__grupo=alumno.grupo
    ).distinct().order_by('nombre')

    grupos_por_nombre = {}
    for m in materias_raw:
        nombre = m.nombre_boleta()
        if nombre not in grupos_por_nombre:
            grupos_por_nombre[nombre] = []
        grupos_por_nombre[nombre].append(m)

    materias_unicas = []
    for nombre_boleta, grupo_materias in sorted(grupos_por_nombre.items()):
        materias_unicas.append({
            'nombre': nombre_boleta,
            'materia_ids': [m.id for m in grupo_materias],
        })

    filas = []
    suma_final_materia = 0
    cuenta_final_materia = 0

    for mat in materias_unicas:
        promedios_trim = []
        suma_materia = 0
        cuenta_materia = 0

        for t in trimestres:
            periodos_eval = t.hijos.filter(tipo='periodo')
            califs = Calificacion.objects.filter(
                alumno=alumno,
                grupo_materia__materia_id__in=mat['materia_ids'],
                periodo__in=periodos_eval,
                calificacion__isnull=False,
            )
            if califs.exists():
                promedio = sum(float(c.calificacion) for c in califs) / califs.count()
                promedio_redondeado = _redondear_calificacion(promedio)
                promedios_trim.append(promedio_redondeado)
                suma_materia += promedio_redondeado
                cuenta_materia += 1
            else:
                promedios_trim.append(None)

        if cuenta_materia > 0:
            promedio_final = _redondear_calificacion(suma_materia / cuenta_materia)
            suma_final_materia += promedio_final
            cuenta_final_materia += 1
        else:
            promedio_final = None

        filas.append({
            'materia': mat['nombre'],
            'trimestres': promedios_trim,
            'promedio_final': promedio_final,
        })

    promedios_por_trimestre = []
    for i in range(len(trimestres)):
        suma = 0
        cuenta = 0
        for fila in filas:
            if fila['trimestres'][i] is not None:
                suma += fila['trimestres'][i]
                cuenta += 1
        promedios_por_trimestre.append(
            _redondear_calificacion(suma / cuenta) if cuenta > 0 else None
        )

    promedio_general_final = (
        _redondear_calificacion(suma_final_materia / cuenta_final_materia)
        if cuenta_final_materia > 0 else None
    )

    config_inst = ConfiguracionInstitucion.get_solo()

    html = render_to_string('horarios/pdf_boleta_trimestral.html', {
        'alumno': alumno,
        'anio_escolar': anio_escolar,
        'trimestres': trimestres,
        'filas': filas,
        'promedios_por_trimestre': promedios_por_trimestre,
        'promedio_general_final': promedio_general_final,
        'config_institucion': config_inst,
        'logo_base64': config_inst.logo_base64(),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boleta_trimestral_{alumno.matricula}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response


@login_required
@requiere_permiso('grupos', 'editar')
def subgrupos_seleccionar(request):
    if request.method == 'POST':
        grupo_id = request.POST.get('grupo')
        return redirect('horarios:subgrupos_grupo', grupo_id=grupo_id)

    grupos = Grupo.objects.all()
    return render(request, 'horarios/subgrupos_seleccionar.html', {'grupos': grupos})


@login_required
@requiere_permiso('subgrupos', 'editar')
def subgrupos_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    # Materias del grupo que tienen al menos un GrupoMateria con subgrupo
    materias_con_subgrupo = Materia.objects.filter(
        grupomateria__grupo=grupo,
        grupomateria__subgrupo__in=['1', '2']
    ).distinct().order_by('nombre')

    if not materias_con_subgrupo.exists():
        return render(request, 'horarios/subgrupos_grupo.html', {
            'grupo': grupo,
            'materias': [],
        })

    materia_id = request.GET.get('materia') or request.POST.get('materia_id')

    materia_sel = None
    if materia_id:
        try:
            materia_sel = materias_con_subgrupo.get(pk=materia_id)
        except Materia.DoesNotExist:
            materia_sel = None

    if not materia_sel:
        materia_sel = materias_con_subgrupo.first()

    # POST: mover alumnos
    if request.method == 'POST':
        alumnos_ids = request.POST.getlist('alumnos')
        subgrupo_destino = request.POST.get('subgrupo_destino')

        if alumnos_ids and subgrupo_destino in ('1', '2'):
            for alumno_id in alumnos_ids:
                try:
                    alumno = Alumno.objects.get(pk=alumno_id, grupo=grupo)
                    AlumnoSubgrupoMateria.objects.update_or_create(
                        alumno=alumno,
                        materia=materia_sel,
                        defaults={'subgrupo': subgrupo_destino}
                    )
                except Alumno.DoesNotExist:
                    continue

            messages.success(request, f'{len(alumnos_ids)} alumno(s) movido(s) al subgrupo {subgrupo_destino}.')

        return redirect(
            f"{reverse('horarios:subgrupos_grupo', kwargs={'grupo_id': grupo.id})}"
            f"?materia={materia_sel.id}"
        )

    # GET: mostrar alumnos divididos por subgrupo efectivo
    alumnos = Alumno.objects.filter(grupo=grupo, activo=True).order_by(
        'apellido_paterno', 'apellido_materno', 'nombre'
    )

    # Excepciones para esta materia
    excepciones = {
        e.alumno_id: e.subgrupo
        for e in AlumnoSubgrupoMateria.objects.filter(materia=materia_sel)
    }

    alumnos_sub1 = []
    alumnos_sub2 = []
    alumnos_sin = []

    for a in alumnos:
        # Subgrupo efectivo: excepción > subgrupo global
        sub_efectivo = excepciones.get(a.id, a.subgrupo)

        if sub_efectivo == '1':
            alumnos_sub1.append(a)
        elif sub_efectivo == '2':
            alumnos_sub2.append(a)
        else:
            alumnos_sin.append(a)

    return render(request, 'horarios/subgrupos_grupo.html', {
        'grupo': grupo,
        'materias': materias_con_subgrupo,
        'materia_sel': materia_sel,
        'alumnos_sub1': alumnos_sub1,
        'alumnos_sub2': alumnos_sub2,
        'alumnos_sin': alumnos_sin,
    })