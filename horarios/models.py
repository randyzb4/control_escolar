from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


# ============================================================
#  Modelos base del sistema académico
# ============================================================

class Profesor(models.Model):
    nombre = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Aula(models.Model):
    TIPOS = [
        ('normal', 'Normal'),
        ('laboratorio', 'Laboratorio'),
        ('taller', 'Taller'),
    ]
    nombre = models.CharField(max_length=50, unique=True)
    capacidad = models.PositiveIntegerField(default=30)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='normal')

    def __str__(self):
        return self.nombre




class Materia(models.Model):
    nombre = models.CharField(max_length=150)
    horas_semanales = models.PositiveIntegerField(default=3)
    requiere_laboratorio = models.BooleanField(default=False)
    materia_padre = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='variantes',
        help_text='Si es una variante (ej: Inglés Nivel 1), apunta a la materia principal'
    )
    es_paralela = models.BooleanField(
        default=False,
        help_text='Indica que esta materia se imparte en paralelo con otra en el mismo horario'
    )

    def nombre_boleta(self):
        if self.materia_padre:
            return self.materia_padre.nombre
        return self.nombre

    def __str__(self):
        return self.nombre



class Grupo(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    materias = models.ManyToManyField(Materia, through='GrupoMateria')

    def __str__(self):
        return self.nombre


class GrupoMateria(models.Model):
    SUBGRUPOS = [
        ('', 'Todo el grupo'),
        ('1', 'Solo subgrupo 1'),
        ('2', 'Solo subgrupo 2'),
    ]
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    profesor = models.ForeignKey(
        Profesor, on_delete=models.SET_NULL, null=True, blank=True
    )
    horas_semanales = models.PositiveIntegerField(default=3)
    subgrupo = models.CharField(
        max_length=2,
        choices=SUBGRUPOS,
        blank=True,
        default='',
        help_text='Si está vacío, aplica a todo el grupo. Si tiene valor, solo al subgrupo indicado.'
    )

    class Meta:
        unique_together = ('grupo', 'materia')

    def aplica_a_alumno(self, alumno):
        """Devuelve True si este GrupoMateria aplica al alumno según su subgrupo."""
        if not self.subgrupo:
            return True
        return alumno.subgrupo == self.subgrupo

    def __str__(self):
        return f"{self.grupo} - {self.materia}"


class DisponibilidadProfesor(models.Model):
    DIAS = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
    ]
    profesor = models.ForeignKey(
        Profesor, on_delete=models.CASCADE, related_name='disponibilidades'
    )
    dia = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        unique_together = ('profesor', 'dia', 'hora_inicio')

    def __str__(self):
        return f"{self.profesor} - {self.get_dia_display()} {self.hora_inicio}-{self.hora_fin}"


class SlotHorario(models.Model):
    DIAS = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
    ]
    dia = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        unique_together = ('dia', 'hora_inicio', 'hora_fin')
        ordering = ['dia', 'hora_inicio']

    def __str__(self):
        return f"{self.get_dia_display()} {self.hora_inicio}-{self.hora_fin}"


class Asignacion(models.Model):
    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='asignaciones'
    )
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    aula = models.ForeignKey(
        Aula, on_delete=models.SET_NULL, null=True, blank=True
    )
    slot = models.ForeignKey(SlotHorario, on_delete=models.CASCADE)
    generado_automaticamente = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profesor', 'slot'],
                name='unique_profesor_slot',
            ),
            models.UniqueConstraint(
                fields=['grupo_materia', 'slot'],
                name='unique_grupo_slot',
            ),
        ]

    def __str__(self):
        return f"{self.grupo_materia} - {self.slot}"

    def clean(self):
        super().clean()

        if self.profesor and self.slot:
            conflicto_profesor = Asignacion.objects.filter(
                profesor=self.profesor,
                slot=self.slot,
            ).exclude(pk=self.pk).exists()
            if conflicto_profesor:
                raise ValidationError(
                    'El profesor ya tiene una clase asignada en este horario.'
                )

        if self.grupo_materia and self.slot:
            otras = Asignacion.objects.filter(
                grupo_materia__grupo=self.grupo_materia.grupo,
                slot=self.slot,
            ).exclude(pk=self.pk)

            for otra in otras:
                gm_actual = self.grupo_materia
                gm_otra = otra.grupo_materia

                # Si alguno NO tiene subgrupo, choca (aplica a todo el grupo)
                if not gm_actual.subgrupo or not gm_otra.subgrupo:
                    raise ValidationError(
                        'El grupo ya tiene una clase asignada en este horario.'
                    )

                # Si ambos tienen subgrupo y es el MISMO, choca
                if gm_actual.subgrupo == gm_otra.subgrupo:
                    raise ValidationError(
                        'El subgrupo ya tiene una clase asignada en este horario.'
                    )

                # Si ambos tienen subgrupo distinto, NO choca (paralelas)

        if self.aula and self.slot:
            conflicto_aula = Asignacion.objects.filter(
                aula=self.aula,
                slot=self.slot,
            ).exclude(pk=self.pk).exists()
            if conflicto_aula:
                raise ValidationError(
                    'El aula ya está ocupada en este horario.'
                )


# ============================================================
#  Autenticación / Roles
# ============================================================

class PerfilUsuario(models.Model):
    ROLES = [
        ('coordinador', 'Coordinador'),
        ('profesor', 'Profesor'),
        ('consulta', 'Consulta'),
    ]
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil'
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='consulta')
    profesor = models.OneToOneField(
        Profesor, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='perfil_usuario',
        help_text='Solo para usuarios con rol profesor'
    )

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"


# ============================================================
#  Configuración global de horario base
# ============================================================

class ConfiguracionHorario(models.Model):
    DIAS_CHOICES = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
        (6, 'Sábado'),
        (7, 'Domingo'),
    ]

    hora_inicio = models.TimeField(default='07:00')
    hora_fin = models.TimeField(default='17:00')
    duracion_bloque = models.PositiveIntegerField(
        default=50,
        help_text='Duración de cada bloque en minutos (ej: 50)'
    )
    dias_activos = models.CharField(
        max_length=20,
        default='1,2,3,4,5',
        help_text='Días separados por coma. Ej: 1,2,3,4,5 = Lunes a Viernes'
    )

    # Recesos opcionales
    receso1_inicio = models.TimeField(
        null=True, blank=True, help_text='Inicio del primer receso (opcional)'
    )
    receso1_fin = models.TimeField(
        null=True, blank=True, help_text='Fin del primer receso (opcional)'
    )
    receso2_inicio = models.TimeField(
        null=True, blank=True, help_text='Inicio del segundo receso (opcional)'
    )
    receso2_fin = models.TimeField(
        null=True, blank=True, help_text='Fin del segundo receso (opcional)'
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Horario'
        verbose_name_plural = 'Configuración de Horario'

    def __str__(self):
        return f"{self.hora_inicio}-{self.hora_fin} cada {self.duracion_bloque}min"

    def lista_dias(self):
        return [int(d) for d in self.dias_activos.split(',') if d.strip().isdigit()]

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def _str_a_time(self, valor):
        from datetime import time as dt_time
        if not valor:
            return None
        if hasattr(valor, 'hour'):
            return valor
        partes = str(valor).split(':')
        return dt_time(int(partes[0]), int(partes[1]))

    def generar_slots(self):
        from datetime import datetime, timedelta

        SlotHorario.objects.all().delete()

        hi = self._str_a_time(self.hora_inicio)
        hf = self._str_a_time(self.hora_fin)
        delta = timedelta(minutes=self.duracion_bloque)

        hoy = datetime.today()
        recesos = []
        for ri, rf in [
            (self.receso1_inicio, self.receso1_fin),
            (self.receso2_inicio, self.receso2_fin),
        ]:
            ri_t = self._str_a_time(ri)
            rf_t = self._str_a_time(rf)
            if ri_t and rf_t and ri_t < rf_t:
                recesos.append((
                    datetime.combine(hoy, ri_t),
                    datetime.combine(hoy, rf_t),
                ))
        recesos.sort(key=lambda r: r[0])

        dias = self.lista_dias()
        inicio = datetime.combine(hoy, hi)
        fin = datetime.combine(hoy, hf)

        creados = 0

        for dia in dias:
            actual = inicio

            while actual + delta <= fin:
                bloque_fin = actual + delta

                receso_encontrado = None
                for r_ini, r_fin in recesos:
                    if actual < r_fin and bloque_fin > r_ini:
                        receso_encontrado = (r_ini, r_fin)
                        break

                if receso_encontrado:
                    r_ini, r_fin = receso_encontrado

                    if actual >= r_ini:
                        actual = r_fin
                        continue

                    if actual < r_ini:
                        duracion_parcial = (r_ini - actual).total_seconds() / 60
                        if duracion_parcial > 0:
                            SlotHorario.objects.create(
                                dia=dia,
                                hora_inicio=actual.time(),
                                hora_fin=r_ini.time(),
                            )
                            creados += 1
                        actual = r_fin
                        continue
                else:
                    SlotHorario.objects.create(
                        dia=dia,
                        hora_inicio=actual.time(),
                        hora_fin=bloque_fin.time(),
                    )
                    creados += 1
                    actual = bloque_fin

        return creados


# ============================================================
#  Alumnos, Períodos y Calificaciones
# ============================================================

class Alumno(models.Model):
    SUBGRUPOS = [
        ('1', 'Subgrupo 1'),
        ('2', 'Subgrupo 2'),
        ('', 'Sin subgrupo'),
    ]
    matricula = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    grupo = models.ForeignKey(
        Grupo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alumnos'
    )
    activo = models.BooleanField(default=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    subgrupo = models.CharField(
        max_length=2,
        choices=SUBGRUPOS,
        blank=True,
        default='',
        help_text='Subgrupo del alumno para materias paralelas (ej: Inglés Nivel 1 vs Nivel 2)'
    )

    class Meta:
        ordering = ['apellido_paterno', 'apellido_materno', 'nombre']

    def __str__(self):
        return f"{self.apellido_paterno} {self.apellido_materno or ''} {self.nombre}".strip()

    def nombre_completo(self):
        partes = [self.nombre, self.apellido_paterno, self.apellido_materno or '']
        return ' '.join(p for p in partes if p).strip()


class Periodo(models.Model):
    TIPOS = [
        ('anual', 'Año escolar'),
        ('trimestre', 'Trimestre'),
        ('periodo', 'Periodo de evaluación'),
    ]

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='anual')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=True)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='hijos')

    def es_periodo(self):
        return self.tipo == 'periodo'

    def periodos_evaluacion(self):
        """Si es un trimestre, devuelve sus periodos de evaluación."""
        if self.es_trimestre():
            return self.hijos.filter(tipo='periodo').order_by('fecha_inicio')
        return Periodo.objects.none()

    def es_trimestre(self):
        return self.tipo == 'trimestre'

    def es_anual(self):
        return self.tipo == 'anual'

    def trimestres(self):
        """Si es un año escolar, devuelve sus trimestres."""
        if self.es_anual():
            return self.hijos.filter(tipo='trimestre').order_by('fecha_inicio')
        return Periodo.objects.none()

    def dias_habiles(self):
        """Cuenta días hábiles (lunes-viernes) entre fecha_inicio y fecha_fin."""
        import calendar
        if not self.fecha_inicio or not self.fecha_fin:
            return 0
        dias = 0
        actual = self.fecha_inicio
        while actual <= self.fecha_fin:
            if actual.weekday() < 5:  # 0=Lun ... 4=Vie
                dias += 1
            actual += __import__('datetime').timedelta(days=1)
        return dias

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"



class Calificacion(models.Model):
    alumno = models.ForeignKey(
        Alumno, on_delete=models.CASCADE, related_name='calificaciones'
    )
    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='calificaciones'
    )
    periodo = models.ForeignKey(
        Periodo, on_delete=models.CASCADE, related_name='calificaciones'
    )
    calificacion = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        help_text='Calificación de 0 a 10 (puede ser decimal)'
    )
    observaciones = models.TextField(blank=True, null=True)
    capturada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calificaciones_capturadas'
    )
    fecha_captura = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('alumno', 'grupo_materia', 'periodo')
        ordering = ['alumno__apellido_paterno', 'grupo_materia__materia__nombre']

    def __str__(self):
        return f"{self.alumno} - {self.grupo_materia.materia} - {self.periodo}: {self.calificacion}"

    def aprobado(self):
        return self.calificacion is not None and self.calificacion >= 6.0

    def color_badge(self):
        if self.calificacion is None:
            return 'secondary'
        if self.calificacion >= 9:
            return 'success'
        if self.calificacion >= 7:
            return 'primary'
        if self.calificacion >= 6:
            return 'warning'
        return 'danger'

class Asistencia(models.Model):
    """
    Registro de asistencia de un alumno en una clase (grupo_materia) en una fecha.
    """
    ESTADOS = [
        ('presente', 'Presente'),
        ('ausente', 'Ausente'),
        ('retardo', 'Retardo'),
        ('justificado', 'Justificado'),
    ]
    alumno = models.ForeignKey(
        Alumno, on_delete=models.CASCADE, related_name='asistencias'
    )
    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='asistencias'
    )
    fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='presente')
    observaciones = models.TextField(blank=True, null=True)
    registrada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asistencias_registradas'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('alumno', 'grupo_materia', 'fecha')
        ordering = ['-fecha', 'alumno__apellido_paterno']

    def __str__(self):
        return f"{self.alumno} - {self.fecha} - {self.get_estado_display()}"

    def color_badge(self):
        colores = {
            'presente': 'success',
            'ausente': 'danger',
            'retardo': 'warning',
            'justificado': 'info',
        }
        return colores.get(self.estado, 'secondary')

class Incidencia(models.Model):
    """
    Bitácora de incidencias: reportes sobre alumnos (conducta, académico, etc.)
    """
    TIPOS = [
        ('conducta', 'Conducta'),
        ('academico', 'Académico'),
        ('asistencia', 'Asistencia'),
        ('otro', 'Otro'),
    ]

    fecha = models.DateField()
    alumno = models.ForeignKey(
        Alumno, on_delete=models.CASCADE, related_name='incidencias'
    )
    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='incidencias'
    )
    tipo_reporte = models.CharField(max_length=20, choices=TIPOS, default='conducta')
    resumen = models.TextField()
    reportado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incidencias_reportadas'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', 'alumno__apellido_paterno']
        verbose_name = 'Incidencia'
        verbose_name_plural = 'Incidencias'

    def __str__(self):
        return f"{self.fecha} - {self.alumno} - {self.get_tipo_reporte_display()}"

    def color_badge(self):
        colores = {
            'conducta': 'danger',
            'academico': 'warning',
            'asistencia': 'info',
            'otro': 'secondary',
        }
        return colores.get(self.tipo_reporte, 'secondary')

class EvidenciaDesempeno(models.Model):
    """
    Evidencia o producto que el profesor define para calificar el desempeño
    de los alumnos de un grupo en una materia y periodo.
    Ejemplo: Tarea 1 (20%), Examen parcial (30%), Proyecto final (50%).
    """
    TIPOS = [
        ('tarea', 'Tarea'),
        ('examen', 'Examen'),
        ('proyecto', 'Proyecto'),
        ('participacion', 'Participación'),
        ('practica', 'Práctica'),
        ('otro', 'Otro'),
    ]

    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='evidencias'
    )
    periodo = models.ForeignKey(
        Periodo, on_delete=models.CASCADE, related_name='evidencias'
    )
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='tarea')
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Porcentaje que vale esta evidencia (ej: 20.00 para 20%)'
    )
    fecha = models.DateField(help_text='Fecha en que se aplicó o entregó')
    descripcion = models.TextField(blank=True, null=True)
    creada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='evidencias_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'nombre']
        verbose_name = 'Evidencia de desempeño'
        verbose_name_plural = 'Evidencias de desempeño'

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"

    def color_badge(self):
        colores = {
            'tarea': 'primary',
            'examen': 'danger',
            'proyecto': 'success',
            'participacion': 'info',
            'practica': 'warning',
            'otro': 'secondary',
        }
        return colores.get(self.tipo, 'secondary')


class CalificacionEvidencia(models.Model):
    evidencia = models.ForeignKey(
        EvidenciaDesempeno, on_delete=models.CASCADE, related_name='calificaciones'
    )
    alumno = models.ForeignKey(
        Alumno, on_delete=models.CASCADE, related_name='calificaciones_evidencias'
    )
    calificacion = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        help_text='Calificación de 0 a 10'
    )
    observaciones = models.TextField(blank=True, null=True)
    capturada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calificaciones_evidencias_capturadas'
    )
    fecha_captura = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    porcentaje_obtenido = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Porcentaje obtenido por el alumno en esta evidencia (0 al valor total de la evidencia)'
    )

    class Meta:
        unique_together = ('evidencia', 'alumno')
        ordering = ['alumno__apellido_paterno', 'evidencia__fecha']

    def __str__(self):
        return f"{self.alumno} - {self.evidencia}: {self.calificacion}"

    def ponderado(self):
        """Devuelve el valor ponderado de esta calificación."""
        if self.calificacion is None:
            return None
        return float(self.calificacion) * float(self.evidencia.porcentaje) / 100

    def color_badge(self):
        if self.calificacion is None:
            return 'secondary'
        if self.calificacion >= 9:
            return 'success'
        if self.calificacion >= 7:
            return 'primary'
        if self.calificacion >= 6:
            return 'warning'
        return 'danger'

    def porcentaje_sobre_valor(self):
        """Devuelve el porcentaje que representa respecto al valor total de la evidencia."""
        if self.porcentaje_obtenido is None:
            return None
        return float(self.porcentaje_obtenido)

class Planeacion(models.Model):
    """
    Planeación didáctica del profesor para un grupo, materia y periodo.
    """
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('publicada', 'Publicada'),
        ('archivada', 'Archivada'),
    ]

    profesor = models.ForeignKey(
        Profesor, on_delete=models.CASCADE, related_name='planeaciones'
    )
    grupo_materia = models.ForeignKey(
        GrupoMateria, on_delete=models.CASCADE, related_name='planeaciones'
    )
    periodo = models.ForeignKey(
        Periodo, on_delete=models.CASCADE, related_name='planeaciones'
    )
    titulo = models.CharField(
        max_length=200, help_text='Título o nombre de la planeación'
    )
    tema = models.CharField(max_length=300, help_text='Tema principal')
    objetivo = models.TextField(help_text='Objetivo general de la planeación')
    fecha_inicio = models.DateField(help_text='Fecha de inicio del periodo a planear')
    fecha_fin = models.DateField(help_text='Fecha de fin del periodo a planear')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    observaciones = models.TextField(blank=True, null=True)
    creada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planeaciones_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_inicio', 'titulo']
        verbose_name = 'Planeación'
        verbose_name_plural = 'Planeaciones'

    def __str__(self):
        return f"{self.titulo} - {self.grupo_materia.grupo.nombre}"

    def color_badge(self):
        colores = {
            'borrador': 'secondary',
            'publicada': 'success',
            'archivada': 'dark',
        }
        return colores.get(self.estado, 'secondary')

    def num_sesiones(self):
        return self.sesiones.count()


class SesionPlaneacion(models.Model):
    """
    Cada sesión de una planeación (una clase específica).
    """
    planeacion = models.ForeignKey(
        Planeacion, on_delete=models.CASCADE, related_name='sesiones'
    )
    numero = models.PositiveIntegerField(help_text='Número de sesión (1, 2, 3...)')
    fecha = models.DateField()
    duracion_minutos = models.PositiveIntegerField(
        default=50, help_text='Duración de la sesión en minutos'
    )
    recursos = models.TextField(
        help_text='Recursos y materiales a usar en la sesión'
    )
    producto = models.TextField(
        help_text='Producto o evidencia que se espera de la sesión'
    )
    actividades = models.TextField(
        blank=True, null=True,
        help_text='Descripción de las actividades (inicio, desarrollo, cierre)'
    )
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['planeacion', 'numero']
        unique_together = ('planeacion', 'numero')
        verbose_name = 'Sesión'
        verbose_name_plural = 'Sesiones'

    def __str__(self):
        return f"Sesión {self.numero} - {self.fecha}"


class EventoCalendario(models.Model):
    """
    Evento del calendario escolar (examen, consejo técnico, evento cívico, etc.)
    """
    TIPOS = [
        ('examen', 'Examen'),
        ('consejo', 'Consejo Técnico'),
        ('evento', 'Evento escolar'),
        ('feriado', 'Día feriado'),
        ('reunion', 'Reunión'),
        ('suspension', 'Suspensión de clases'),
        ('otro', 'Otro'),
    ]

    fecha = models.DateField()
    fecha_fin = models.DateField(
        null=True, blank=True,
        help_text='Si el evento dura varios días'
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='evento')
    todo_el_dia = models.BooleanField(
        default=True,
        help_text='Si no tiene hora específica'
    )
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_creados'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'hora_inicio']
        verbose_name = 'Evento del calendario'
        verbose_name_plural = 'Eventos del calendario'

    def __str__(self):
        return f"{self.fecha} - {self.titulo}"

    def color_badge(self):
        colores = {
            'examen': 'danger',
            'consejo': 'warning',
            'evento': 'primary',
            'feriado': 'secondary',
            'reunion': 'info',
            'suspension': 'dark',
            'otro': 'secondary',
        }
        return colores.get(self.tipo, 'secondary')

    def color_hex(self):
        colores = {
            'examen': '#e74c3c',
            'consejo': '#f39c12',
            'evento': '#3498db',
            'feriado': '#95a5a6',
            'reunion': '#17a2b8',
            'suspension': '#2c3e50',
            'otro': '#6c757d',
        }
        return colores.get(self.tipo, '#6c757d')

class ConfiguracionInstitucion(models.Model):
    """
    Configuración global de la institución. Solo debe existir una fila.
    """
    nombre_institucion = models.CharField(
        max_length=200,
        default='Mi Institución Educativa',
        help_text='Nombre oficial de la institución'
    )
    logo = models.ImageField(
        upload_to='institucion/',
        null=True, blank=True,
        help_text='Logo de la institución (se usará en los PDFs)'
    )
    direccion = models.CharField(
        max_length=300, blank=True, null=True,
        help_text='Dirección de la institución'
    )
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    sitio_web = models.URLField(blank=True, null=True)
    ciclo_escolar = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Ej: 2025-2026'
    )
    lema = models.CharField(
        max_length=300, blank=True, null=True,
        help_text='Lema o misión corta de la institución'
    )
    director = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Nombre del director o responsable'
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de la Institución'
        verbose_name_plural = 'Configuración de la Institución'

    def __str__(self):
        return self.nombre_institucion

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def logo_url(self):
        """Devuelve la URL del logo o None si no existe."""
        if self.logo:
            return self.logo.url
        return None

    def logo_path(self):
        """Devuelve la ruta absoluta del logo (para PDFs)."""
        if self.logo:
            return self.logo.path
        return None

    def logo_base64(self):
        """Devuelve el logo en formato base64 para incrustarlo en PDFs."""
        import base64
        if not self.logo:
            return None
        try:
            with open(self.logo.path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
                ext = self.logo.name.lower().split('.')[-1]
                mime = 'image/png'
                if ext in ('jpg', 'jpeg'):
                    mime = 'image/jpeg'
                elif ext == 'gif':
                    mime = 'image/gif'
                elif ext == 'svg':
                    mime = 'image/svg+xml'
                return f"data:{mime};base64,{data}"
        except Exception:
            return None