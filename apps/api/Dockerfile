FROM python:3.13-slim

WORKDIR /srv/docfetch

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATABASE_URL=postgresql+psycopg://docfetch:docfetch@db:5432/docfetch
ENV DATA_DIR=/data
ENV APP_ENV=development

RUN mkdir -p /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]