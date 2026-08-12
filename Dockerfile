FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better Docker layer caching — only reinstalls
# when requirements.txt actually changes, not on every code edit)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code
COPY app.py .
COPY prism_schemas.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
