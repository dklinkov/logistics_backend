import os
from django.core.exceptions import ImproperlyConfigured


def _require_env(name):
    """Raise an error if the environment variable isn't defined"""
    value = os.getenv(name)
    if value is None:
        raise ImproperlyConfigured('Required environment variable "{}" is not set.'.format(name))
    return value


def act(act_type, serials, equipments, systems, issue_location, objects):
    """Создание массива для последующей записи в шаблон акта"""
    # Берем количество серийных номеров в качестве длины массива (серийный номер обязательное поля для каждой записи)
    n = len(serials)
    items = []
    # Для разных типов актов используются разные шаблоны с отличающимися полями
    if act_type in ["return_sc", 'return_company', 'issue_company', 'return_in_zip']:
        for i in range(n):
            items.append((i + 1, equipments[i], serials[i], systems[i]))
    else:
        if act_type == 'repair':
            for i in range(n):
                items.append((i + 1, objects[i], equipments[i], serials[i], systems[i]))
        else:
            if act_type == 'issue_from_zip':
                for i in range(n):
                    items.append((i + 1, equipments[i], serials[i], systems[i], issue_location[i]))
            else:
                if act_type == 'issue_sc':
                    for i in range(n):
                        items.append((i + 1, equipments[i], serials[i], systems[i], issue_location[i]))
    return items
