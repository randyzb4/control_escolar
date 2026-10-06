from django.urls import path
from . import views

app_name = 'horarios'

urlpatterns = [
    # Autenticación
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('generar/', views.ejecutar_generacion, name='generar'),

    # Grupos
    path('grupos/', views.lista_grupos, name='lista_grupos'),
    path('grupos/<int:grupo_id>/', views.horario_grupo, name='horario_grupo'),
    path('grupos/<int:grupo_id>/pdf/', views.pdf_horario_grupo, name='pdf_horario_grupo'),

    # Profesores
    path('profesores/', views.lista_profesores, name='lista_profesores'),
    path('profesores/<int:profesor_id>/', views.horario_profesor, name='horario_profesor'),
    path('profesores/<int:profesor_id>/pdf/', views.pdf_horario_profesor, name='pdf_horario_profesor'),

    # Reportes
    path('carga-profesores/', views.carga_profesores, name='carga_profesores'),
    path('resumen/', views.resumen, name='resumen'),
    path('asignaciones/', views.lista_asignaciones, name='lista_asignaciones'),

    # Configuración
    path('configurar-horario/', views.configurar_horario, name='configurar_horario'),

    # Portal del profesor
    path('mi-horario/', views.mi_horario, name='mi_horario'),
    path('mis-grupos/', views.mis_grupos, name='mis_grupos'),
    path('capturar-calificaciones/', views.capturar_calificaciones, name='capturar_calificaciones'),
    path('pase-lista/', views.pase_lista, name='pase_lista'),
    path('mi-bitacora/', views.mi_bitacora, name='mi_bitacora'),

    # Carga masiva de alumnos
    path('cargar-alumnos/', views.cargar_alumnos, name='cargar_alumnos'),
    path('descargar-plantilla-alumnos/', views.descargar_plantilla_alumnos, name='descargar_plantilla_alumnos'),

    path('alumnos/<int:alumno_id>/boleta/', views.boleta_alumno, name='boleta_alumno'),
    path('alumnos/<int:alumno_id>/boleta/pdf/', views.pdf_boleta_alumno, name='pdf_boleta_alumno'),
    path('grupos/<int:grupo_id>/alumnos/', views.lista_alumnos_grupo, name='lista_alumnos_grupo'),
    path('api/materias-por-grupo/', views.materias_por_grupo, name='materias_por_grupo'),
    path('grupos/<int:grupo_id>/calificaciones/', views.calificaciones_grupo, name='calificaciones_grupo'),
    path('grupos/<int:grupo_id>/calificaciones/pdf/', views.pdf_calificaciones_grupo, name='pdf_calificaciones_grupo'),
    path('grupos/<int:grupo_id>/asistencias/', views.asistencias_grupo, name='asistencias_grupo'),
    path('grupos/<int:grupo_id>/asistencias/pdf/', views.pdf_asistencias_grupo, name='pdf_asistencias_grupo'),
    path('bitacoras/incidencias/', views.incidencias_lista, name='incidencias_lista'),
    path('bitacoras/incidencias/nueva/', views.incidencia_crear, name='incidencia_crear'),
    path('bitacoras/incidencias/<int:incidencia_id>/editar/', views.incidencia_editar, name='incidencia_editar'),
    path('bitacoras/incidencias/<int:incidencia_id>/eliminar/', views.incidencia_eliminar, name='incidencia_eliminar'),
    path('api/alumnos-por-gm/', views.alumnos_por_gm, name='alumnos_por_gm'),
    path('bitacoras/desempeno/', views.desempeno_seleccionar, name='desempeno_seleccionar'),
    path('bitacoras/desempeno/grupo/<int:grupo_id>/', views.desempeno_grupo, name='desempeno_grupo'),
    path('bitacoras/desempeno/grupo/<int:grupo_id>/evidencia/nueva/', views.evidencia_crear, name='evidencia_crear'),
    path('bitacoras/desempeno/evidencia/<int:evidencia_id>/editar/', views.evidencia_editar, name='evidencia_editar'),
    path('bitacoras/desempeno/evidencia/<int:evidencia_id>/eliminar/', views.evidencia_eliminar, name='evidencia_eliminar'),
    path('bitacoras/desempeno/evidencia/<int:evidencia_id>/capturar/', views.capturar_desempeno, name='capturar_desempeno'),
    path('planeaciones/', views.planeaciones_lista, name='planeaciones_lista'),
    path('planeaciones/nueva/', views.planeacion_crear, name='planeacion_crear'),
    path('planeaciones/<int:planeacion_id>/editar/', views.planeacion_editar, name='planeacion_editar'),
    path('planeaciones/<int:planeacion_id>/ver/', views.planeacion_ver, name='planeacion_ver'),
    path('planeaciones/<int:planeacion_id>/eliminar/', views.planeacion_eliminar, name='planeacion_eliminar'),
    path('planeaciones/<int:planeacion_id>/sesion/nueva/', views.sesion_crear, name='sesion_crear'),
    path('planeaciones/sesion/<int:sesion_id>/editar/', views.sesion_editar, name='sesion_editar'),
    path('planeaciones/sesion/<int:sesion_id>/eliminar/', views.sesion_eliminar, name='sesion_eliminar'),
    path('planeaciones/<int:planeacion_id>/pdf/', views.pdf_planeacion, name='pdf_planeacion'),
    path('desempeno/mandar-boleta/<int:alumno_id>/<int:gm_id>/<int:periodo_id>/', views.mandar_desempeno_a_boleta, name='mandar_desempeno_a_boleta'),
    path('reportes/', views.reportes, name='reportes'),
    path('grupos/<int:grupo_id>/lista-asistencia/pdf/', views.pdf_lista_asistencia, name='pdf_lista_asistencia'),
    path('desempeno/pendientes/<int:grupo_id>/', views.desempeno_pendientes, name='desempeno_pendientes'),
    path('calendario/', views.calendario, name='calendario'),
    path('calendario/evento/nuevo/', views.evento_crear, name='evento_crear'),
    path('calendario/evento/<int:evento_id>/editar/', views.evento_editar, name='evento_editar'),
    path('calendario/evento/<int:evento_id>/eliminar/', views.evento_eliminar, name='evento_eliminar'),
    path('calendario/pdf/', views.pdf_calendario, name='pdf_calendario'),
    path('configuracion/', views.configuracion_institucion, name='configuracion_institucion'),
    path('grupos/<int:grupo_id>/alumnos/nuevo/', views.alumno_crear, name='alumno_crear'),
    path('alumnos/<int:alumno_id>/editar/', views.alumno_editar, name='alumno_editar'),
    path('alumnos/<int:alumno_id>/eliminar/', views.alumno_eliminar, name='alumno_eliminar'),
    path('alumnos/<int:alumno_id>/cambiar-grupo/', views.alumno_cambiar_grupo, name='alumno_cambiar_grupo'),
    path('alumnos/<int:alumno_id>/boleta-trimestral/', views.boleta_trimestral, name='boleta_trimestral'),
    path('alumnos/<int:alumno_id>/boleta-trimestral/pdf/', views.pdf_boleta_trimestral, name='pdf_boleta_trimestral'),
    path('subgrupos/', views.subgrupos_seleccionar, name='subgrupos_seleccionar'),
    path('subgrupos/grupo/<int:grupo_id>/', views.subgrupos_grupo, name='subgrupos_grupo'),
    path('api/alumnos-por-grupo/', views.alumnos_por_grupo, name='alumnos_por_grupo'),





]