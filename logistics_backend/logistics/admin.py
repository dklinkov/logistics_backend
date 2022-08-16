from django.contrib import admin
from . import models
# Register your models here.
# admin.site.register(models.Main)
# admin.site.register(models.Spares)
admin.site.register(models.Location)
admin.site.register(models.Systems)
admin.site.register(models.Equipments)
admin.site.register(models.RepairPlace)
admin.site.register(models.Employees)
admin.site.register(models.ActType)
admin.site.register(models.Acts)
admin.site.register(models.ActsMain)
admin.site.register(models.ActsSpares)

