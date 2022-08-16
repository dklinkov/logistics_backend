from django.db import models


class Systems(models.Model):
    """Типы систем"""
    class Meta:
        db_table = 'systems'
        verbose_name = 'Типы систем'

    system = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.system


class Location(models.Model):
    """Наименование объекта"""
    class Meta:
        db_table = 'location'
        verbose_name = 'Наименование объекта'

    location = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.location


class RepairPlace(models.Model):
    """Место ремонта"""
    class Meta:
        db_table = 'repair_place'
        verbose_name = 'Место ремонта'

    place = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.place


class Equipments(models.Model):
    """Тип оборудования"""
    class Meta:
        db_table = 'equipments'
        verbose_name = 'Тип оборудования'

    equipment = models.CharField(max_length=100, unique=True)
    equipment_system = models.ForeignKey(Systems, on_delete=models.RESTRICT,
                                         verbose_name='Идентификатор системы')
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.equipment


class Employees(models.Model):
    """Сотрудники"""
    class Meta:
        db_table = 'employees'
        verbose_name = 'Сотрудники'
        unique_together = ('last_name', 'first_name', 'middle_name')

    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, null=True, blank=True)
    organization = models.CharField(max_length=100, null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        result = self.last_name + ' ' + self.first_name + ' ' + self.middle_name
        return result


class Spares(models.Model):
    """Запасные части и принадлежности"""
    class Meta:
        db_table = 'spares'
        verbose_name = 'Запасные части и принадлежности'

    object = models.ForeignKey(Location, on_delete=models.RESTRICT, related_name="spares_location_name",
                               verbose_name='Идентификатор объекта')
    name = models.ForeignKey(Equipments, on_delete=models.RESTRICT, related_name="spares_equipment_name",
                             verbose_name='Идентификатор оборудования')
    serial = models.CharField(max_length=100, null=True, blank=True)
    issued_dt = models.DateField(null=True, blank=True)
    system = models.ForeignKey(Systems, on_delete=models.RESTRICT, related_name="spares_system_name",
                               verbose_name='Идентификатор системы')
    serial_spare = models.CharField(max_length=100, null=True, blank=True)
    returned_dt = models.DateField(null=True, blank=True)
    comments = models.TextField(max_length=500, null=True, blank=True)


class Main(models.Model):
    """Основная таблица"""
    class Meta:
        db_table = 'main'
        verbose_name = 'Основная таблица'

    object = models.ForeignKey(Location, on_delete=models.RESTRICT, related_name="location_name",
                               verbose_name='Идентификатор объекта')
    name = models.ForeignKey(Equipments, on_delete=models.RESTRICT, related_name="equipment_name",
                             verbose_name='Идентификатор оборудования')
    serial = models.CharField(max_length=100, null=True, blank=True)
    system = models.ForeignKey(Systems, on_delete=models.RESTRICT, related_name="system_name",
                               verbose_name='Идентификатор системы')
    accepted_dt = models.DateField(null=True, blank=True)
    shipped_repair_dt = models.DateField(null=True, blank=True)
    accepted_repair_dt = models.DateField(null=True, blank=True)
    issued_object = models.ForeignKey(Location, on_delete=models.RESTRICT, related_name='issued_location_name',
                                      verbose_name='Идентификатор объекта', null=True, blank=True)
    serial2 = models.CharField(max_length=100, null=True, blank=True)
    issued_dt = models.DateField(null=True, blank=True)
    repair_place = models.ForeignKey(RepairPlace, on_delete=models.RESTRICT, related_name="repair_name",
                                     verbose_name='Идентификатор места ремонта', null=True, blank=True)
    comments = models.TextField(max_length=500, null=True, blank=True)
    responsible_employee = models.ForeignKey(Employees, on_delete=models.RESTRICT, related_name="employee_name",
                                             verbose_name='Идентификатор сотрудника', null=True, blank=True)


class ActType(models.Model):
    """Тип акта"""

    class Meta:
        db_table = 'act_type'
        verbose_name = 'Типы актов'

    act = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.act


class Acts(models.Model):
    """Основная таблица актов"""

    class Meta:
        db_table = 'acts'
        verbose_name = 'Акты'

    act_type = models.ForeignKey(ActType, on_delete=models.RESTRICT, related_name="act_type", verbose_name='Тип акта')
    act_path = models.CharField(max_length=500)


class ActsMain(models.Model):
    """Акты общей таблицы"""

    class Meta:
        db_table = 'acts_main'
        verbose_name = 'Акты общей таблицы'

    act = models.ForeignKey(Acts, on_delete=models.RESTRICT, related_name="act_main", verbose_name='Акт')
    main = models.ForeignKey(Main, on_delete=models.RESTRICT, related_name="main_id", verbose_name='Запись в таблице')


class ActsSpares(models.Model):
    """Акты ЗИП"""

    class Meta:
        db_table = 'acts_spares'
        verbose_name = 'Акты ЗИП'

    act = models.ForeignKey(Acts, on_delete=models.RESTRICT, related_name="act_spares", verbose_name='Акт')
    spares = models.ForeignKey(Spares, on_delete=models.RESTRICT,
                               related_name="main_id", verbose_name='Запись в таблице')
