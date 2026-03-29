FROM python:3.10
WORKDIR /app
COPY . /app
RUN apt-get update && apt-get install -y
RUN pip install --no-cache-dir flask flask-cors
EXPOSE 5005
CMD ["python", "app.py"]
