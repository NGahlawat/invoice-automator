FROM python:3.12-slim

WORKDIR /app


# --------------------------------------------------
# PYTHON SETTINGS
# --------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# --------------------------------------------------
# INSTALL PYTHON PACKAGES
# --------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


# --------------------------------------------------
# INSTALL PLAYWRIGHT CHROMIUM
# --------------------------------------------------

RUN python -m playwright install --with-deps chromium


# --------------------------------------------------
# COPY PROJECT
# --------------------------------------------------

COPY . .


# --------------------------------------------------
# FOLDERS USED BY APP
# --------------------------------------------------

RUN mkdir -p /app/output
RUN mkdir -p /app/uploads


# --------------------------------------------------
# FLASK PORT
# --------------------------------------------------

EXPOSE 5000


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]