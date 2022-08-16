import boto3  # Работа с хранилищем S3
import docx  # Работа с документами MS Word
import os
import base64
from . import logistic_serializers  # Импорт своих сериализаторов
from . import models  # Импорт своих моделей
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db.models import F  # Для дополнения результатов запроса в БД данными их связанных таблиц
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser  # Аутентификация
from rest_framework_swagger.views import get_swagger_view  # Автодокументирование API
from collections import OrderedDict  # Требуется для разбора сериализованных данных
from collections import defaultdict
from datetime import date, datetime
from docxtpl import DocxTemplate  # Работа с документами MS Word
from django.http import HttpResponse  # HTTP ответы
from botocore.client import Config  # Работа с хранилищем S3
from .utils import _require_env, act


_aws_access_key_id = _require_env('aws_access_key_id')
_aws_secret_access_key = _require_env('aws_secret_access_key')
_endpoint_url = _require_env('endpoint_url')


# Create your views here.

# Автодокументирование схемы API
schema_view = get_swagger_view(title='Logistics API')


class ActUploadView(APIView):
    """Загрузка сканов актов в хранилище"""

    # Определение разрешений для использования (авторизованные пользователи)
    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):
        try:
            # print(request.body)
            # Определение времени создания (уникальный идентификатор)
            creation_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Подключение к хранилищу
            try:
                s3 = boto3.resource('s3', endpoint_url=_endpoint_url,
                                    aws_access_key_id=_aws_access_key_id,
                                    aws_secret_access_key=_aws_secret_access_key,
                                    config=Config(signature_version='s3v4'),
                                    region_name='ru-krd-01')
            except Exception as exc:
                return HttpResponse(exc, content_type='text/plain', status=status.HTTP_424_FAILED_DEPENDENCY)
                # return Response(status=status.HTTP_424_FAILED_DEPENDENCY)
            # Определение возможных типов актов по разделам (основной, ЗИП)
            acts_main = ["scan_issue_act", "scan_return_act", "scan_repair_act"]
            acts_spares = ["scan_return_zip", "scan_issue_zip"]
            # Получение файла из запроса
            up_file = request.data["file"]
            # Получение ID записей к которым относится акт
            id_values = request.data["id"]
            type_act = request.data["type"]
            # Сопоставление типа акта с названием на русском для формирования читаемого имени
            if type_act == "issue_act":
                rus_name = "Акт_Выдачи"
            elif type_act == "return_act":
                rus_name = "Акт_Приема"
            elif type_act == "repair_act":
                rus_name = "Акт_Отправки_в_ремонт"
            elif type_act == "return_zip":
                rus_name = "Акт_Приема_ЗИП"
            elif type_act == "issue_zip":
                rus_name = "Акт_Выдачи_ЗИП"
            else:
                return HttpResponse("Unknown act type!", content_type='text/plain')
            # Определение имени файла с добавлением времени создания и типа акта (для типа отбрасываем расширение)
            filename = "scan_" + rus_name + "_" + creation_time + ".pdf"
            act_type = "scan_" + type_act
            # Запись данных в файл в локальной папке
            filepath = os.path.join(os.path.dirname(__file__), 'acts_scan', filename)
            file = open(filepath, 'wb')
            # print("File opened - ", filepath)
            try:
                file.write(base64.b64decode(up_file))
            except Exception as exc:
                print(exc)
            # print("File writen - ", filepath)
            file.close()
            # print("File closed - ", filepath)
            # Сохранение файла в хранилище S3
            try:
                s3.Bucket('logistic').upload_file(filepath, "/acts_scan/" + filename)
                # print("S3 SAVED")
            except Exception as exc:
                print(exc)
            # Удаление файла из локальной папки
            os.remove(filepath)
            # Поиск в БД ID типа акта
            act_types = models.ActType.objects.values()
            act_type_id = False
            for raw in act_types:
                if raw["act"][:8] == act_type[:8]:
                    act_type_id = raw["id"]
            if act_type_id:
                pass
            else:
                return HttpResponse("Unknown act type!", content_type='text/plain')
            # Сохранение в БД (в общей таблице всех актов) информации о загруженном файле
            act_query = models.Acts.objects.create(act_path=filename, act_type_id=act_type_id)
            act_query.save()
            # Получение ID нового акта
            act_id = act_query.pk
            # print("ACT ID CREATED - ", act_id)
            # Сохранение в БД (в таблицу общего раздела) информации о файле
            if act_type in acts_main:
                for raw_id in id_values:
                    act_data = models.ActsMain.objects.create(act_id=act_id, main_id=raw_id)
                    act_data.save()
                    # print("ActsMain RAW CREATED")
            # Или сохранение в БД (в таблицу раздела ЗИП) информации о файле
            elif act_type in acts_spares:
                for raw_id in id_values:
                    act_data = models.ActsSpares.objects.create(act_id=act_id, main_id=raw_id)
                    act_data.save()
            else:
                return HttpResponse("Акт не относится к имеющимся таблицам",
                                    content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)
            # Ответ об успешном выполнении запроса
            return Response(filename, status.HTTP_201_CREATED)
        # Если что-то пошло не так, валим все на фронтендера и его кривой запрос
        # для debug режима обертку try-except лучше убрать
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)
            # return Response(status=status.HTTP_400_BAD_REQUEST)


class GetAct(APIView):
    """Работа с актами"""

    # Определение разрешений для использования (авторизованные пользователи)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Формирование актов на основе данных из БД по ID полей основной таблицы и таблицы ЗИП"""
        # print(request.data)
        # Подключение к хранилищу S3
        try:
            s3 = boto3.resource('s3', endpoint_url=_endpoint_url,
                                aws_access_key_id=_aws_access_key_id,
                                aws_secret_access_key=_aws_secret_access_key,
                                config=Config(signature_version='s3v4'),
                                region_name='ru-krd-01')
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_424_FAILED_DEPENDENCY)
            # return Response(status=status.HTTP_424_FAILED_DEPENDENCY)
        # Проверка метода запроса
        if request.method == 'POST':
            # Определение текущей даты
            today = date.today()
            # Определение типов актов для основной таблицы и таблицы ЗИП
            acts_main = ["issue_company", "return_company", "issue_sc", "return_sc", "repair"]
            acts_spares = ["return_in_zip", "issue_from_zip"]
            # Получение ID записей таблиц из запроса
            id_values = request.data.get("id")
            # Получение наименования объекта, представитель которого сдает/получает оборудование
            location = request.data.get("location")
            # Получение типа акта
            act_type = request.data.get("act_type")
            # Сопоставление типа акта с названием на русском для формирования читаемого имени
            if act_type == "issue_company":
                rus_name = "Акт_Выдачи_Вилион"
            elif act_type == "return_company":
                rus_name = "Акт_Приема_Вилион"
            elif act_type == "issue_sc":
                rus_name = "Акт_Выдачи_СЦ1"
            elif act_type == "return_sc":
                rus_name = "Акт_Приема_СЦ1"
            elif act_type == "repair":
                rus_name = "Акт_Отправки_в_ремонт"
            elif act_type == "return_in_zip":
                rus_name = "Акт_Приема_ЗИП"
            elif act_type == "issue_from_zip":
                rus_name = "Акт_Выдачи_ЗИП"
            else:
                return HttpResponse("Unknown act type!", content_type='text/plain')
            # Получение ФИО выдающего сотрудника
            issue_employee = request.data.get("issue_employee")
            # Получение ФИО принимающего сотрудника
            receive_employee = request.data.get("receive_employee")
            # Определение шаблона для типа акта
            act_template = act_type + "_template.docx"
            # Создание списков для данных из БД
            serials = []
            systems = []
            equipments = []
            repair_places = []
            issue_location = []
            locations = []
            # Определение времени формирования акта (текущее время, уникальный идентификатор)
            creation_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Получение списка типов актов из таблицы БД
            act_types = models.ActType.objects.values()
            # Определение соответствия переданного типа акта, имеющемуся в таблице типов в БД
            act_type_id = False
            for raw in act_types:
                if raw["act"][:3] == act_type[:3]:
                    act_type_id = raw["id"]
            if act_type_id:
                pass
            else:
                return HttpResponse("Unknown act type!", content_type='text/plain')
            # Запись в общую таблицу актов в БД информации о новом акте, его имени и типе
            act_query = models.Acts.objects.create(act_path=rus_name + "_" + creation_time + '.docx',
                                                   act_type_id=act_type_id)
            act_query.save()
            # Получение ID созданной записи
            act_id = act_query.pk
            # Определение принадлежности типа акта к основной таблице или таблице ЗИП
            # Если акт относится к основной таблице
            if act_type in acts_main:
                # Для типа акта "отправка в ремонт" поле представителя объекта делаем пустым (пожелание заказчика)
                if "repair" in act_type:
                    location = " "
                # Для каждой записи таблицы получаем необходимы данные для внесения в акт
                for raw_id in id_values:
                    # Получаем запись из таблицы
                    data = models.Main.objects.filter(id=raw_id)
                    serialized = logistic_serializers.MainSerializer(data, many=True)
                    # Переводим ее в словарь
                    serialized_data = dict(serialized.data[0])
                    # print(serialized_data)
                    # Добавляем серийные номера в список серийных номеров
                    serials.append(serialized_data['serial'])
                    # Добавляем наименование оборудования в список
                    equipments.append(dict(serialized_data['name'])['equipment'])
                    # Добавляем наименования систем в список
                    systems.append(dict(serialized_data['system'])['system'])
                    # Добавляем наименования объектов в список
                    locations.append(dict(serialized_data['object'])['location'])
                    # Если поле "выдан объекту" в таблице пустое, то добавляем в список пустое значение
                    # для соблюдения порядка и длины списков
                    try:
                        issue_location.append(dict(serialized_data['issued_object'])['location'])
                    except:
                        issue_location.append(" ")
                    # Если поле "место ремонта" в таблице пустое, то добавляем в список пустое значение
                    # для соблюдения порядка и длины списков
                    try:
                        repair_places.append(dict(serialized_data['repair_place'])['place'])
                    except:
                        repair_places.append(" ")
                    # Добавляем в таблицу в поле "дата выдачи" текущую дату (пожелание заказчика)
                    # if "issue" in act_type:
                    #     data.update(issued_dt=today)
                    # elif "repair" in act_type:
                    #     data.update(shipped_repair_dt=today)
                    # Добавляем запись об акте в таблицу актов, относящихся к общей таблице
                    act_data = models.ActsMain.objects.create(act_id=act_id, main_id=raw_id)
                    act_data.save()
            # Если акт относится к таблице ЗИП
            elif act_type in acts_spares:
                # Для каждой записи таблицы получаем необходимы данные для внесения в акт
                for raw_id in id_values:
                    # Получаем запись из таблицы
                    data = models.Spares.objects.filter(id=raw_id)
                    serialized = logistic_serializers.MainSerializer(data, many=True)
                    # Переводим ее в словарь
                    serialized_data = dict(serialized.data[0])
                    # Запоняем списки (подробнее описано в блоке выше)
                    serials.append(serialized_data['serial'])
                    equipments.append(dict(serialized_data['name'])['equipment'])
                    systems.append(dict(serialized_data['system'])['system'])
                    locations.append(dict(serialized_data['object'])['location'])
                    try:
                        issue_location.append(dict(serialized_data['issued_object'])['location'])
                    except:
                        issue_location.append(" ")
                    try:
                        repair_places.append(dict(serialized_data['repair_place'])['place'])
                    except:
                        repair_places.append(" ")
                    # Добавляем запись об акте в таблицу актов, относящихся к
                    act_data = models.ActsSpares.objects.create(act_id=act_id, main_id=raw_id)
                    act_data.save()
                    # Добавляем в таблицу в поле "дата выдачи" текущую дату (пожелание заказчика)
                    # if "issue" in act_type:
                    #     data.update(issued_dt=today)
                    # elif "return" in act_type:
                    #     data.update(returned_dt=today)
            # Если принадлежность акта к таблице не определилась, сообщаем об ошибке в запросе
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            # Создаем файл акта в локальной папке
            filename = os.path.join(os.path.dirname(__file__), 'acts', rus_name + "_" + creation_time + '.docx')
            # Создаем временный файл для обработки таблицы (особенности работы с MS Word)
            temp_filename = os.path.join(os.path.dirname(__file__), 'acts',
                                         rus_name + "_" + creation_time + '_temp.docx')
            # Передаем в функцию списки сформированные из данных, полученных из БД по ID из запроса
            # получаем готовые данные для записи в шаблок акта
            items = act(act_type, serials, equipments, systems, issue_location, locations)
            # Открываем шаблон акта в соответствии с типом акта
            doc = docx.Document(os.path.join(os.path.dirname(__file__), 'acts_templates', act_template))
            # Формируем таблицу в шаблоне акта
            for table in doc.tables:
                for row in items:
                    cells = table.add_row().cells
                    for i, item in enumerate(row):
                        cells[i].text = str(item)
            # Определяем набор не табличных данных для внесения в акт
            context = {'issue_employee': issue_employee, 'location': location,
                       'receive_employee': receive_employee, 'date': str(today), 'pieces': len(serials)}
            # Сохраняем таблицу во временный файл
            doc.save(temp_filename)
            # Открываем временный файл с заполненной таблицей
            doc1 = DocxTemplate(temp_filename)
            # Вносим не табличные данные
            doc1.render(context)
            # Сохраняем готовый файл акта со всеми необходимыми данными
            doc1.save(filename)
            # Удаляем временный файл
            os.remove(temp_filename)
            # Загружаем итоговый файл акта в хранилище S3
            s3.Bucket('logistic').upload_file(filename, "/acts/" + rus_name + "_" + creation_time + '.docx')
            # Формируем ответ с готовым файлом для скачивания пользователем
            with open(filename, 'rb') as doc:  # read as binary  'application/vnd.ms-word'
                content = doc.read()  # Read the file
                response = HttpResponse(content, content_type='application/blob')
                response['Content-Disposition'] = 'attachment; filename=' + rus_name + "_" + creation_time + '.docx'
                # response['Content-Length'] = len(content)  # calculate length of content
                response['Access-Control-Allow-Origin'] = '*'
            # Удаляем файл акта из локальной папки
            os.remove(filename)
            # Отправляем файл пользователю на скачивание
            return response

    def get(self, request):
        """Получение имеющихся актов из хранилища S3"""

        # Подключение к хранилищу S3
        try:
            s3 = boto3.resource('s3', endpoint_url=_endpoint_url,
                                aws_access_key_id=_aws_access_key_id,
                                aws_secret_access_key=_aws_secret_access_key,
                                config=Config(signature_version='s3v4'),
                                region_name='ru-krd-01')
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_424_FAILED_DEPENDENCY)
        # Обрабатываем запрос
        try:
            # Определяем, запрошен скан или MS Word файл акта (лежат в разных папках в хранилище S3)
            if "scan" in self.request.query_params.get("act_path"):
                # Определяем имя файла из запроса
                filename = os.path.join(os.path.dirname(__file__), 'acts_scan',
                                        self.request.query_params.get("act_path"))
                # Скачиваем файл в локальную папку
                s3.Bucket('logistic').download_file("/acts_scan/" + self.request.query_params.get("act_path"),
                                                           filename)
            else:
                # Определяем имя файла из запроса
                filename = os.path.join(os.path.dirname(__file__), 'acts', self.request.query_params.get("act_path"))
                # Скачиваем файл в локальную папку
                s3.Bucket('logistic').download_file("/acts/" + self.request.query_params.get("act_path"),
                                                           filename)
            # Формируем ответ с готовым файлом для скачивания пользователем
            with open(filename, 'rb') as doc:  # read as binary  'application/vnd.ms-word'
                content = doc.read()  # Read the file
                response = HttpResponse(content, content_type='application/blob')
                response['Content-Disposition'] = 'attachment; filename=' + self.request.query_params.get("act_path")
                response['Access-Control-Allow-Origin'] = '*'
            # Удаляем файл акта из локальной папки
            os.remove(filename)
            # Отправляем файл пользователю на скачивание
            return response
        # Если не удалось, возвращаем ошибку, вероятно запрос некорректный
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)


class MainView(APIView):
    permission_classes = (IsAuthenticated,)
    """Работа с основной таблицей (GET, POST, PUT, DELETE)"""

    def get(self, request):
        """Получение данных из основной таблицы"""
        # print(request.query_params)
        # Создаем словарь для аргументов поискового запроса
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['id', 'serial', 'serial2', 'comments']
        # Поля с датами
        dt_fields = ['accepted_dt', 'shipped_repair_dt', 'accepted_repair_dt', 'issued_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system', 'issued_object', 'repair_place', 'responsible_employee']
        # Добавочные поля для поиска по названиям в полях со внешними ключами
        add_fields = ['system_name', 'location_name', 'equipment_name', 'issued_object_name',
                      'repair_place_name', 'responsible_employee_name']
        # Получаем все данные из таблицы и названия по внешним ключам
        data = models.Main.objects.select_related(*fk_fields).annotate(
            system_name=F('system__system'),
            location_name=F('object__location'),
            equipment_name=F('name__equipment'),
            issued_object_name=F('issued_object__location'),
            repair_place_name=F('repair_place__place'),
            responsible_employee_name=F('responsible_employee__last_name'), )
        # Получаем данные из запроса для поиска необходимых записей
        for field in fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        for field in dt_fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        for field in fk_fields:
            if self.request.query_params.get(field):
                arguments[field] = self.request.query_params.get(field)
        for field in add_fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        # Если запрос содержал данные для поиска
        if len(arguments) > 0:
            # Выбираем данные из общей таблицы по параметрам поискового запроса
            filtered_data = data.filter(**arguments)
            # Сериализуем полученные данные
            serialized = logistic_serializers.MainSerializer(filtered_data, many=True)
            # Выбираем ID записей, удовлетворяющих поисковому запросу в отдельный список
            ids = []
            for item in serialized.data:
                item_id = dict(item)["id"]
                ids.append(item_id)
            # Получаем данные о всех актах
            acts = models.ActsMain.objects.filter(main_id__in=ids)
            acts_serialized = logistic_serializers.ActsMainSerializer(acts, many=True)
            # Формируем из нах словарь для дальнейшей обработки
            acts_dict = defaultdict(list)
            # Добавляем одну пустую запись на случай если ни в одной из записей нет сведений об актах
            acts_dict["acts"].append({"act_id": "", "act_path": "", "main_id": ""})
            # Заполняем словарь данными об актах
            for item in acts_serialized.data:
                act_id = dict(dict(item)["act"])["id"]
                act_path = dict(dict(item)["act"])["act_path"]
                act_main_id = dict(dict(item)["main"])["id"]
                acts_dict["acts"].append({"act_id": act_id, "act_path": act_path, "main_id": act_main_id})
            # Дополняем данные из общей таблицы данными об актах, относящихся к каждой записи
            main_data = serialized.data
            acts_dict = dict(acts_dict)
            # Сопоставляем ID записей основной таблицы с ID актов, относящихся к ней и добавляем к каждой записи
            # основной таблицы имена актов, которые отнесены к этой записи
            for raw in main_data:
                acts_names = []
                for item in acts_dict['acts']:
                    if raw['id'] == item['main_id']:
                        if item['act_path'][-1] == 'f':
                            type_end = -19
                        else:
                            type_end = -20
                        acts_names.append({"act_name": item['act_path'], "act_type": item['act_path'][:type_end]})
                print(acts_names)
                raw.update({"acts": acts_names})
        # Если поисковый запрос не содержал параметров для поиска
        else:
            # Получаем все записи основной таблицы
            serialized = logistic_serializers.MainSerializer(data, many=True)
            # Выбираем ID всех записей
            ids = []
            for item in serialized.data:
                item_id = dict(item)["id"]
                ids.append(item_id)
            # Получаем данные о всех актах
            acts = models.ActsMain.objects.filter(main_id__in=ids)
            acts_serialized = logistic_serializers.ActsMainSerializer(acts, many=True)
            # Формируем из нах словарь для дальнейшей обработки
            acts_dict = defaultdict(list)
            # Добавляем одну пустую запись на случай если ни в одной из записей нет сведений об актах
            acts_dict["acts"].append({"act_id": "", "act_path": "", "main_id": ""})
            # Заполняем словарь данными об актах
            for item in acts_serialized.data:
                act_id = dict(dict(item)["act"])["id"]
                act_path = dict(dict(item)["act"])["act_path"]
                act_main_id = dict(dict(item)["main"])["id"]
                acts_dict["acts"].append({"act_id": act_id, "act_path": act_path, "main_id": act_main_id})
            # Дополняем данные из общей таблицы данными об актах, относящихся к каждой записи
            main_data = serialized.data
            acts_dict = dict(acts_dict)
            # Сопоставляем ID записей основной таблицы с ID актов, относящихся к ней и добавляем к каждой записи
            # основной таблицы имена актов, которые отнесены к этой записи
            for raw in main_data:
                acts_names = []
                for item in acts_dict['acts']:
                    if raw['id'] == item['main_id']:
                        if item['act_path'][-1] == 'f':
                            type_end = -19
                        else:
                            type_end = -20
                        acts_names.append({"act_name": item['act_path'], "act_type": item['act_path'][:type_end]})
                raw.update({"acts": acts_names})
        # Возвращаем сформированный набор данных общей таблицы с добавленными данными об актах к каждой записи
        return Response(main_data, status=status.HTTP_200_OK)

    def post(self, request):
        """Добавление записи в основную таблицу"""
        # Создаем словарь для аргументов запроса на добавление записи
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['serial', 'serial2', 'comments', 'accepted_dt',
                  'shipped_repair_dt', 'accepted_repair_dt', 'issued_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system', 'issued_object',
                     'repair_place', 'responsible_employee']
        # Для обычных полей, при наличии данных в запросе добавляем их в словарь аргументов
        for field in fields:
            if request.data.get(field):
                arguments[field] = request.data.get(field)
        # Для полей со внешними ключами добавляем к имени поля _id для корректной записи в БД
        for field in fk_fields:
            try:
                if request.data.get(field).get("id"):
                    arguments[field + '_id'] = request.data.get(field).get("id")
            except:
                pass
        # print(request.data)
        # Пробуем сохранить полученные данные в БД
        try:
            query = models.Main.objects.create(**arguments)
            query.save()
            # Если все получилось, сообщаем, что запись создана
            return Response(status=status.HTTP_201_CREATED)
        # Если запись не удалась, получаем ошибку и возвращаем ее пользователю
        except:
            query = models.Main.objects.create(**arguments)
            return Response(query.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Внесение изменений/дополнений в запись основной таблицы"""
        # print(request.data)
        # Получаем ID записи для изменения
        item_id = request.data['id']
        # Создаем словарь для аргументов запроса на изменение/дополнение записи
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['serial', 'serial2', 'comments', 'accepted_dt',
                  'shipped_repair_dt', 'accepted_repair_dt', 'issued_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system', 'issued_object',
                     'repair_place', 'responsible_employee']
        # Для обычных полей, при наличии данных в запросе добавляем их в словарь аргументов
        for field in fields:
            # Если в запросе есть данные для поля, добавляем их в словарь
            if request.data.get(field):
                arguments[field] = request.data.get(field)
            # Если данных нет, значит пользователь их удалил или не заполнил, очищаем данное поле
            else:
                arguments[field] = None
        # Для полей со внешними ключами
        for field in fk_fields:
            # Если в запросе есть данные о поле, получаем ID для этого поля
            if request.data.get(field):
                try:
                    if request.data.get(field).get("id"):
                        arguments[field] = request.data.get(field).get("id")
                except:
                    pass
            # Если данных нет, значит пользователь их удалил или не заполнил, очищаем данное поле
            else:
                arguments[field] = None
        # print(arguments)
        # Пробуем внести изменение/дополнение в запись
        try:
            models.Main.objects.filter(id=item_id).update(**arguments)
            # Если все получилось, сообщаем, что изменения/дополнения принять
            return Response(status=status.HTTP_202_ACCEPTED)
        # Если запись не удалась, получаем ошибку и возвращаем ее пользователю
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Удаление записи из основной таблицы"""
        # Получаем ID записи для удаления
        item_id = request.data['id']
        # Получаем запись по ID
        item = models.Main.objects.get(id=item_id)
        # Если такая запись есть, удаляем
        if item:
            item.delete()
            return Response(status=status.HTTP_202_ACCEPTED)
        # Если нет, сообщаем пользователю, что запись не найдена
        else:
            return HttpResponse("Запись не найдена!", content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)


class SparesView(APIView):
    """Работа с таблицей запасных частей (GET, POST, PUT, DELETE)"""

    permission_classes = (IsAuthenticated,)
    def get(self, request):
        """Получение данных из таблицы ЗИП"""
        # Создаем словарь для аргументов поискового запроса
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['id', 'serial', 'serial_spare', 'comments']
        # Поля с датами
        dt_fields = ['issued_dt', 'returned_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system']
        # Добавочные поля для поиска по названиям в полях со внешними ключами
        add_fields = ['system_name', 'location_name', 'equipment_name']
        # Получаем все данные из таблицы и названия по внешним ключам
        data = models.Spares.objects.select_related(*fk_fields).annotate(
            system_name=F('system__system'),
            location_name=F('object__location'),
            equipment_name=F('name__equipment'))  #
        # Получаем данные из запроса для поиска необходимых записей
        for field in fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        for field in dt_fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        for field in fk_fields:
            if self.request.query_params.get(field):
                arguments[field] = self.request.query_params.get(field)
        for field in add_fields:
            if self.request.query_params.get(field):
                arguments[field + "__contains"] = self.request.query_params.get(field)
        # Если запрос содержал данные для поиска
        if len(arguments) > 0:
            # Выбираем данные из таблицы ЗИП по параметрам поискового запроса
            serialized = logistic_serializers.SparesSerializer(data.filter(**arguments), many=True)
            # Выбираем ID записей, удовлетворяющих поисковому запросу в отдельный список
            ids = []
            for item in serialized.data:
                item_id = dict(item)["id"]
                ids.append(item_id)
            # Получаем данные о всех актах
            acts = models.ActsSpares.objects.filter(spares_id__in=ids)
            acts_serialized = logistic_serializers.ActsSparesSerializer(acts, many=True)
            # Формируем из нах словарь для дальнейшей обработки
            acts_dict = defaultdict(list)
            # Добавляем одну пустую запись на случай если ни в одной из записей нет сведений об актах
            acts_dict["acts"].append({"act_id": "", "act_path": "", "spares_id": ""})
            # Заполняем словарь данными об актах
            for item in acts_serialized.data:
                act_id = dict(dict(item)["act"])["id"]
                act_path = dict(dict(item)["act"])["act_path"]
                act_spares_id = dict(dict(item)["spares"])["id"]
                acts_dict["acts"].append({"act_id": act_id, "act_path": act_path, "spares_id": act_spares_id})
            # Дополняем данные из таблицы ЗИП данными об актах, относящихся к каждой записи
            spare_data = serialized.data
            acts_dict = dict(acts_dict)
            # Сопоставляем ID записей таблицы ЗИП с ID актов, относящихся к ней и добавляем к каждой записи
            # основной таблицы имена актов, которые отнесены к этой записи
            for raw in spare_data:
                acts_names = []
                for item in acts_dict['acts']:
                    if raw['id'] == item['spares_id']:
                        if item['act_path'][-1] == 'f':
                            type_end = -19
                        else:
                            type_end = -20
                        acts_names.append({"act_name": item['act_path'], "act_type": item['act_path'][:type_end]})
                raw.update({"acts": acts_names})
        # Если поисковый запрос не содержал параметров для поиска
        else:
            # Выбираем все данные из таблицы ЗИП
            serialized = logistic_serializers.SparesSerializer(data, many=True)
            # Выбираем ID записей
            ids = []
            for item in serialized.data:
                item_id = dict(item)["id"]
                ids.append(item_id)
            # Получаем данные о всех актах
            acts = models.ActsSpares.objects.all()
            acts_serialized = logistic_serializers.ActsSparesSerializer(acts, many=True)
            # Формируем из нах словарь для дальнейшей обработки
            acts_dict = defaultdict(list)
            # Добавляем одну пустую запись на случай если ни в одной из записей нет сведений об актах
            acts_dict["acts"].append({"act_id": "", "act_path": "", "spares_id": ""})
            # Заполняем словарь данными об актах
            for item in acts_serialized.data:
                act_id = dict(dict(item)["act"])["id"]
                act_path = dict(dict(item)["act"])["act_path"]
                act_spares_id = dict(dict(item)["spares"])["id"]
                acts_dict["acts"].append({"act_id": act_id, "act_path": act_path, "spares_id": act_spares_id})
            # Дополняем данные из таблицы ЗИП данными об актах, относящихся к каждой записи
            spare_data = serialized.data
            acts_dict = dict(acts_dict)
            # Сопоставляем ID записей таблицы ЗИП с ID актов, относящихся к ней и добавляем к каждой записи
            # основной таблицы имена актов, которые отнесены к этой записи
            for raw in spare_data:
                acts_names = []
                for item in acts_dict['acts']:
                    if raw['id'] == item['spares_id']:
                        if item['act_path'][-1] == 'f':
                            type_end = -19
                        else:
                            type_end = -20
                        acts_names.append({"act_name": item['act_path'], "act_type": item['act_path'][:type_end]})
                raw.update({"acts": acts_names})
        # Возвращаем сформированный набор данных таблицы ЗИП с добавленными данными об актах к каждой записи
        return Response(spare_data, status=status.HTTP_200_OK)

    def post(self, request):
        """Добавление записи в таблицу ЗИП"""
        # Создаем словарь для аргументов запроса на добавление записи
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['id', 'serial', 'serial_spare', 'comments', 'issued_dt', 'returned_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system']
        # Для обычных полей, при наличии данных в запросе добавляем их в словарь аргументов
        for field in fields:
            if request.data.get(field):
                arguments[field] = request.data.get(field)
        # Для полей со внешними ключами добавляем к имени поля _id для корректной записи в БД
        for field in fk_fields:
            try:
                if request.data.get(field).get("id"):
                    arguments[field + '_id'] = request.data.get(field).get("id")
            except:
                pass
        # Пробуем сохранить полученные данные в БД
        try:
            query = models.Spares.objects.create(**arguments)
            query.save()
            # Если все получилось, сообщаем, что запись создана
            return Response(status=status.HTTP_201_CREATED)
        # Если запись не удалась, получаем ошибку и возвращаем ее пользователю
        except:
            query = models.Spares.objects.create(**arguments)
            return Response(query.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Внесение изменений/дополнений в запись таблицы ЗИП"""
        # print(request.data)
        # Получаем ID записи для изменения
        item_id = request.data['id']
        # Создаем словарь для аргументов запроса на изменение/дополнение записи
        arguments = {}
        # Определяем типы полей основной таблицы
        # Обычные поля
        fields = ['id', 'serial', 'serial_spare', 'comments', 'issued_dt', 'returned_dt']
        # Поля со внешними ключами
        fk_fields = ['object', 'name', 'system']
        # Для обычных полей, при наличии данных в запросе добавляем их в словарь аргументов
        for field in fields:
            # Если в запросе есть данные для поля, добавляем их в словарь
            if request.data.get(field):
                arguments[field] = request.data.get(field)
            # Если данных нет, значит пользователь их удалил или не заполнил, очищаем данное поле
            else:
                arguments[field] = None
        # Для полей со внешними ключами
        for field in fk_fields:
            # Если в запросе есть данные о поле, получаем ID для этого поля
            if request.data.get(field):
                try:
                    if request.data.get(field).get("id"):
                        arguments[field] = request.data.get(field).get("id")
                except:
                    pass
            # Если данных нет, значит пользователь их удалил или не заполнил, очищаем данное поле
            else:
                arguments[field] = None
        # Пробуем внести изменение/дополнение в запись
        try:
            models.Spares.objects.filter(id=item_id).update(**arguments)
            return Response(status=status.HTTP_202_ACCEPTED)
        # Если запись не удалась, получаем ошибку и возвращаем ее пользователю
        except Exception as exc:
            return HttpResponse(exc, content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Удаление записи из таблицы ЗИП"""
        # Получаем ID записи для удаления
        item_id = request.data['id']
        # Получаем запись по ID
        item = models.Spares.objects.get(id=item_id)
        # Если такая запись есть, удаляем
        if item:
            item.delete()
            return Response(status=status.HTTP_202_ACCEPTED)
        # Если нет, сообщаем пользователю, что запись не найдена
        else:
            return HttpResponse("Запись не найдена!", content_type='text/plain', status=status.HTTP_400_BAD_REQUEST)


class ReferenceView(APIView):
    """Работа с таблицами справочников (GET, POST, PUT, DELETE)"""

    permission_classes = (IsAuthenticated,)
    # Функция выдачи данных со всех справочников в формате JSON
    def get(self, request):
        """Получение данных из справочников"""
        # Получаем и сериализуем данные из всех справочников в БД
        location_serialized = logistic_serializers.LocationSerializer(models.Location.objects.all(), many=True)
        system_serialized = logistic_serializers.SystemsSerializer(models.Systems.objects.all(), many=True)
        equipment_serialized = logistic_serializers.EquipmentsSerializer(models.Equipments.objects.all(), many=True)
        repair_serialized = logistic_serializers.RepairPlaceSerializer(models.RepairPlace.objects.all(), many=True)
        employee_serialized = logistic_serializers.EmployeesSerializer(models.Employees.objects.all(), many=True)
        # Возвращаем данные всех справочников в виде одного словаря со вложенностями
        return Response({"location": location_serialized.data, "system": system_serialized.data,
                         "equipment": equipment_serialized.data, "repair": repair_serialized.data,
                         "employee": employee_serialized.data})

    # Функция добавления данных в справочники (прием запроса в формате JSON),

    def post(self, request):
        """Добавление данных в справочник"""
        # print(request.data)
        # Выбор справочника на основе имени поля в переданном запросе и формирование запроса на запись в БД
        if 'location' in request.data.keys():
            serializer = logistic_serializers.LocationSerializer(data=request.data)
        elif 'system' in request.data.keys():
            serializer = logistic_serializers.SystemsSerializer(data=request.data)
        elif 'equipment' in request.data.keys():
            query = models.Equipments.objects.create(equipment=request.data.get("equipment"),
                                                     equipment_system_id=request.data.get("equipment_system").get("id"))
            query.save()
            return Response(status=status.HTTP_201_CREATED)
        elif 'repair' in request.data.keys():
            serializer = logistic_serializers.RepairPlaceSerializer(data={'place': request.data.get('repair')})
        else:
            serializer = logistic_serializers.EmployeesSerializer(data=request.data)
        # Пробуем сохранить созданный запрос в БД
        try:
            # Если запрос корректный сохраняем
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Если что-то пошло не так, возвращаем данные об ошибке
        except:
            pass
        # print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Функция изменения данных в справочниках (прием запроса в формате JSON),

    def put(self, request):
        """Изменение данных в справочниках"""
        # Получение ID записи для изменения
        item_id = request.data['id']
        # выбор справочника на основе имени поля в переданном запросе, выбор записи для изменений на основе поля ID.
        if 'location' in request.data.keys():
            item = models.Location.objects.get(id=item_id)
            serializer = logistic_serializers.LocationSerializer(instance=item, data=request.data, partial=True)
        elif 'system' in request.data.keys():
            item = models.Systems.objects.get(id=item_id)
            serializer = logistic_serializers.SystemsSerializer(instance=item, data=request.data, partial=True)
        elif 'equipment' in request.data.keys():
            models.Equipments.objects.filter(id=item_id).update(equipment=request.data.get("equipment"),
                                                                equipment_system_id=request.data.get(
                                                                    "equipment_system").get("id"),
                                                                active=request.data.get("active"))
            return Response(status=status.HTTP_202_ACCEPTED)
        elif 'place' in request.data.keys():
            item = models.RepairPlace.objects.get(id=item_id)
            serializer = logistic_serializers.RepairPlaceSerializer(instance=item, data=request.data, partial=True)
        else:
            item = models.Employees.objects.get(id=item_id)
            serializer = logistic_serializers.EmployeesSerializer(instance=item, data=request.data, partial=True)
        # Пробуем сохранить созданный запрос в БД
        try:
            # Если запрос корректный сохраняем
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        except:
            pass
        # Если что-то пошло не так, возвращаем данные об ошибке
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Функция удаления данных из справочника (прием запроса в формате JSON),
    # выбор справочника на основе имени поля в переданном запросе, выбор записи для удаления на основе поля ID.
    # def delete(self, request):
    #     item_id = request.data['id']
    #     if 'location' in request.data.keys():
    #         item = Location.objects.get(id=item_id)
    #     elif 'system' in request.data.keys():
    #         item = Systems.objects.get(id=item_id)
    #     elif 'equipment' in request.data.keys():
    #         item = Equipments.objects.get(id=item_id)
    #     elif 'place' in request.data.keys():
    #         item = RepairPlace.objects.get(id=item_id)
    #     else:
    #         item = Employees.objects.get(id=item_id)
    #     if item:
    #         item.delete()
    #         return Response(status=status.HTTP_202_ACCEPTED)
    #     else:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)
