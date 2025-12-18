FROM python:3.10-slim

WORKDIR /app

# dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# code
COPY . .

# port Fly
EXPOSE 8080

# lancement API
CMD ["uvicorn", "smartcoach_api.api:app", "--host", "0.0.0.0", "--port", "8080"]