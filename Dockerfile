FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/datasets /data/model_artifacts

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py recover_runs --all && python manage.py runserver 0.0.0.0:8000"]