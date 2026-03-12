FROM python:3.11-slim

WORKDIR /app

# System deps for PyMuPDF and other native packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p data/uploads data/vector_store data/experience_library data/synthetic

EXPOSE 8000 8501

# Default: start FastAPI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
