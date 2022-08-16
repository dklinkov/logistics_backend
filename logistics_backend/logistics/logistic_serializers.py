from . import models
from rest_framework import serializers


# Сериализатор для справочника типов систем
class SystemsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Systems
        fields = '__all__'


# Сериализатор для справочника названий объектов
class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Location
        fields = '__all__'


# Сериализатор для справочника названий ремонтных мастерских
class RepairPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RepairPlace
        fields = '__all__'


# Сериализатор для справочника названий оборудования
class EquipmentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Equipments
        depth = 1
        fields = '__all__'


# Сериализатор для справочника сотрудников
class EmployeesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Employees
        fields = '__all__'


# Сериализатор для таблицы запасных частей и принадлежностей
class SparesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Spares
        depth = 1
        fields = '__all__'


# Сериализатор для основной таблицы
class MainSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Main
        depth = 1
        fields = ("id", "serial", "accepted_dt", "shipped_repair_dt", "accepted_repair_dt",
                  "serial2", "issued_dt", "comments", "object", "name", "system", "issued_object",
                  "repair_place", "responsible_employee")


# class MainSerializerPost(serializers.ModelSerializer):
#     name = EquipmentsSerializer()
#     system = SystemsSerializer()
#     issued_object = LocationSerializer()
#     object = LocationSerializer()
#     repair_place = RepairPlaceSerializer()
#     responsible_employee = EmployeesSerializer()
#
#     class Meta:
#         model = models.Main
#         depth = 1
#         fields = ("serial", "accepted_dt", "shipped_repair_dt", "accepted_repair_dt",
#                   "serial2", "issued_dt", "comments", "object", "name", "system", "issued_object",
#                   "repair_place", "responsible_employee")

# Сериализатор для таблицы ипов актов
class ActTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ActType
        fields = '__all__'


# Сериализатор для общей таблицы актов
class ActsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Acts
        depth = 1
        fields = '__all__'


# Сериализатор для актов основной таблицы
class ActsMainSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ActsMain
        depth = 1
        fields = '__all__'


# Сериализатор для актов таблицы ЗИП
class ActsSparesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ActsSpares
        depth = 1
        fields = '__all__'
