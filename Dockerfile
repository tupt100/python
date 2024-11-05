FROM python:3.7
ENV PYTHONUNBUFFERED 1

RUN apt-get update -y && apt-get install -y libproj-dev gdal-bin

WORKDIR /opt/services/app/src

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --no-input