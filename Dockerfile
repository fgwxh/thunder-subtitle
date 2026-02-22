FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn jinja2 python-multipart httpx typer rich questionary pysmb openai watchdog tzdata

COPY src ./src
COPY static ./static
COPY templates ./templates
COPY run_fastapi_ui.py .
COPY ui_config.example.json .
COPY download_history.json .

ENV PYTHONPATH=/app/src
ENV HOST=0.0.0.0
ENV PORT=8010

EXPOSE 8010

CMD ["python", "run_fastapi_ui.py"]
