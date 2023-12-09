FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py clearml_api.py database.py main.py .

CMD ["python", "main.py"]
