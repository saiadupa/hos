FROM python:3.8

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV MYSQL_DATABASE=mydb
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=S@i@@12345
ENV MYSQL_HOST=db

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["flask", "run"]
