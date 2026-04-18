FROM python:3.12-slim

WORKDIR /app

# Install cron (busybox cron via cronie/dcron is not in slim; use vixie-cron)
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

COPY scraper.py server.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Daily 06:00 scraper run
RUN echo "0 6 * * * python3 /app/scraper.py >> /proc/1/fd/1 2>&1" \
    > /etc/cron.d/nachrichten \
    && chmod 0644 /etc/cron.d/nachrichten \
    && crontab /etc/cron.d/nachrichten

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
