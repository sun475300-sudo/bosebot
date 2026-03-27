FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs data

EXPOSE 8080

CMD ["python", "web_server.py", "--port", "8080"]
