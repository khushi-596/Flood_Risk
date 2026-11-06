FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install Python dependencies
COPY services/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/api /workspace

# Copy data, models, config, and infra needed at runtime
COPY data/seeds            /workspace/data/seeds
COPY data/known_flood_locations.csv /workspace/data/known_flood_locations.csv
COPY models                /workspace/models
COPY config                /workspace/config
COPY infra                 /workspace/infra
COPY alembic.ini           /workspace/alembic.ini

# Create uploads directory
RUN mkdir -p /workspace/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
