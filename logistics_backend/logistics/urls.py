from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView,)
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


app_name = 'logistics'
schema_view = get_schema_view(
   openapi.Info(
      title="Logistics API",
      default_version='v1',
      description="Logistics API",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('main/', views.MainView.as_view(), name='Главная таблица'),
    path('spares/', views.SparesView.as_view(), name='Таблица запасных частей'),
    path('references/', views.ReferenceView.as_view(), name='Справочники'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('get_act/', views.GetAct.as_view()),
    path('upload_act/', views.ActUploadView.as_view()),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

urlpatterns = format_suffix_patterns(urlpatterns)
