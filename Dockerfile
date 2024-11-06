FROM python:3.9

ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    libproj-dev \
    gdal-bin \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/services/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python3 manage.py collectstatic --no-input

#CMD ["python3", "manage.py", "runserver"]
#CMD ["bash", "-c", "pgunicorn --workers 3 --preload --timeout 120 --keep-alive 30 --log-level debug --bind 0.0.0.0:8000 config.wsgi"]
CMD ["gunicorn", "--bind 0.0.0.0:8000", "nmbl.wsgi"]

