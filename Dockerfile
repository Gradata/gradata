FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Create a default brain directory
RUN mkdir -p /brain

ENV BRAIN_DIR=/brain

ENTRYPOINT ["python", "-c", "from gradata.brain import Brain; b = Brain('/brain'); print(f'Gradata brain ready at /brain')"]
