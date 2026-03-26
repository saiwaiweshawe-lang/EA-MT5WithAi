FROM python:3.11-slim

LABEL maintainer="saiweiweshawe@gmail.com"
LABEL description="量化交易系统 V1.0.0"

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash trader \
    && usermod -aG gpio,i2c,spi trader

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R trader:trader /app

USER trader

EXPOSE 5000

VOLUME ["/app/config", "/app/logs", "/app/data"]

CMD ["python", "main.py", "--api"]
