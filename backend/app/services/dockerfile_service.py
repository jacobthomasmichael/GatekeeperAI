_TEMPLATES: dict[str, str] = {
    "python-streamlit": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app
ENV HOME=/tmp
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
""",
    "python-gradio": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app
ENV HOME=/tmp
USER appuser
EXPOSE 7860
CMD ["python", "app.py"]
""",
    "python-web": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app
ENV HOME=/tmp
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
    "python": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app
ENV HOME=/tmp
USER appuser
CMD ["python", "main.py"]
""",
    "nodejs-next": """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
RUN npm run build && chown -R node:node /app
ENV HOME=/tmp
USER node
EXPOSE 3000
CMD ["npm", "start"]
""",
    "nodejs": """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
RUN chown -R node:node /app
ENV HOME=/tmp
USER node
EXPOSE 3000
CMD ["node", "index.js"]
""",
    "static": """\
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
""",
}

_FALLBACK = """\
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app
ENV HOME=/tmp
USER appuser
CMD ["python", "main.py"]
"""


def generate_dockerfile(detected_type: str | None) -> str:
    return _TEMPLATES.get(detected_type or "", _FALLBACK)
