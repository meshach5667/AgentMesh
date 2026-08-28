FROM python:3.12-slim as backend

WORKDIR /app/server
COPY server/requirements.txt .
RUN pip install -r requirements.txt
COPY server/ .

FROM node:20 as frontend
WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci
COPY client/ .
RUN npm run build

FROM backend as runner
COPY --from=frontend /app/client/out /app/client/out
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
