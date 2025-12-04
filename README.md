# Prueba Técnica IA

API construida con **FastAPI** que cubre:

1. **Parte 1** – Autenticación JWT, cargas CSV a **AWS S3**, validación y persistencia en **SQL Server**.
2. **Parte 2** – Módulo web para análisis de documentos (PDF/JPG/PNG) con **AWS Textract** + IA local (Hugging Face) y un histórico exportable a Excel.

## Requerimientos cubiertos

- `POST /auth/login`: JWT firmado con `id_usuario`, `rol`, `iat` y expiración de 15 minutos.
- `POST /files/upload`: CSV + parámetros extra → validaciones, guardado en S3 y SQL Server, resumen IA.
- `POST /auth/refresh`: renueva el token si aún no expira.
- `POST /documents/analyze`: clasifica (Factura/Información), extrae datos con Textract, genera resumen/sentimiento local y almacena resultado + eventos.
- `GET /history/events` y `GET /history/events/export`: histórico filtrable y exportable (Excel).
- Interfaces web: `/web/analysis` (carga de documentos) y `/web/history` (log de eventos).

## Configuración

1. Python 3.11+
2. Instalar dependencias:
   ```bash
   pip install -e .
   ```
3. Variables de entorno (ver `.env.example`):
   - `JWT_SECRET_KEY`
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_S3_BUCKET`
   - `SQLSERVER_URI` (ODBC)
   - `AI_MODEL` (opcional, default `google/flan-t5-small`)
   - `APP_TIMEZONE` (opcional, default `UTC`, ej. `America/Argentina/Buenos_Aires`)
4. Ejecutar:
   ```bash
   uvicorn app.main:app --reload
   ```

> Para ambientes locales sin Textract/S3/SQL Server puedes usar LocalStack y contenedores de SQL Server. El modelo Hugging Face se descarga la primera vez (requiere Internet); luego funciona offline.

## Uso rápido

### Parte 1

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"rol":"data_uploader"}'

curl -X POST http://localhost:8000/files/upload \
  -H "Authorization: Bearer <TOKEN>" \
  -F "param_a=campaña" \
  -F "param_b=lote-1" \
  -F "file=@data.csv"

curl -X POST http://localhost:8000/auth/refresh \
  -H "Authorization: Bearer <TOKEN>"
```

### Parte 2

- Abre `http://localhost:8000/web/analysis` para cargar PDF/JPG/PNG.
- Abre `http://localhost:8000/web/history` para consultar y exportar eventos.
- API:
  ```bash
  curl -X POST http://localhost:8000/documents/analyze \
    -H "Authorization: Bearer <TOKEN>" \
    -F "file=@documento.pdf"

  curl http://localhost:8000/history/events \
    -H "Authorization: Bearer <TOKEN>"
  ```

## IA en el proyecto

- **Validación CSV**: `AIInsightsService` usa `transformers` (`google/flan-t5-small`) para generar resúmenes locales sin costo ni claves.
- **Documentos**: `AWS Textract` procesa PDF/imagenes. Luego `transformers` genera resumen e identificamos sentimiento con `pipeline("sentiment-analysis")`.

## Histórico y exportación

Cada evento relevante (carga, análisis IA, interacciones) se guarda en `event_logs`.  
Los filtros y exportación a Excel (`historial.xlsx`) se ejecutan desde `/history/events` y `/history/events/export`.

## GitHub

```bash
git init
git add .
git commit -m "feat: implementar APIs FastAPI + módulos IA"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin master
```


