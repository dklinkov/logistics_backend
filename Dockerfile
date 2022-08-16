FROM python:3

ENV PYTHONUNBUFFERED 1

RUN mkdir /code
WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

RUN pip uninstall -y pyjwt

RUN pip uninstall -y jwt

RUN pip install jwt

RUN pip install pyjwt

COPY . .

EXPOSE 8001

CMD ["python","vilion_logistics/manage.py","makemigrations","logistics"]

CMD ["python","vilion_logistics/manage.py","migrate","logistics"]

CMD ["python","vilion_logistics/manage.py","runserver","0.0.0.0:8001"]

