# footymodel — container image. Works on Render, Railway, Fly.io, anywhere.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better build caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project (app.py, engine.py, sources.py, static/, etc.)
COPY . .

# Hosting platforms inject $PORT; default to 8000 for local `docker run`
ENV PORT=8000
EXPOSE 8000

# Start the API + UI. Shell form so $PORT expands at runtime.
CMD uvicorn app:app --host 0.0.0.0 --port $PORT
