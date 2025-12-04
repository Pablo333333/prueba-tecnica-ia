# Prueba Técnica IA

API construida con **FastAPI** para resolver el flujo completo de autenticación vía JWT, carga y validación de archivos CSV con persistencia en **SQL Server**, almacenamiento en **AWS S3** e insights generados con un modelo open-source de **Hugging Face** (sin necesidad de API keys pagas).

## Requerimientos cubiertos

- `POST /auth/login`: genera un JWT firmado con `id_usuario`, `rol`, `iat` y expiración de 15 minutos.
- `POST /files/upload`: recibe CSV + `param_a` y `param_b`, valida contenido, guarda el archivo en S3, procesa filas en SQL Server y devuelve el detalle de validaciones más un resumen generado con IA.
- `POST /auth/refresh`: solo con tokens vigentes, entrega un nuevo JWT con tiempo de expiración extendido.

## Estructura principal

```
app/
├── api/routes       # Enrutadores de FastAPI
├── core             # Configuración y utilidades de seguridad
├── db               # Sesiones y creación de tablas
├── models           # Modelos SQLAlchemy (UploadedFile / UploadedRow)
├── schemas          # Modelos Pydantic para request/response
└── services         # Integraciones (S3, AI, validaciones)
```

## Configuración

1. Python 3.11+
2. Instala dependencias:
   ```bash
   pip install -e .
   ```
3. Variables de entorno requeridas:
   - `JWT_SECRET_KEY` (mínimo 32 caracteres)
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_S3_BUCKET`
   - `SQLSERVER_URI` (cadena `mssql+pyodbc:///?odbc_connect=...`)
   - `AI_MODEL` (opcional, por defecto `google/flan-t5-small`)
4. Ejecuta la API:
   ```bash
   uvicorn app.main:app --reload
   ```

> Para ambientes locales sin SQL Server o S3 disponibles, puedes usar herramientas como [localstack](https://github.com/localstack/localstack) y contenedores SQL Server (`mcr.microsoft.com/mssql/server`).

## Flujo de carga

1. Autenticarte en `/auth/login`.
2. Invocar `/files/upload` (tipo `multipart/form-data`) con:
   - `file`: CSV con encabezados
   - `param_a`, `param_b`: parámetros extra solicitados
3. La respuesta incluye:
   - `validations`: lista de reglas aplicadas (vacíos, duplicados, etc.)
   - `ai_summary`: insight generado por la clase `AIInsightsService`
   - Metadatos de persistencia (id, `s3_key`, timestamp)

## Renovación de token

Enviar `POST /auth/refresh` con el `Authorization: Bearer <token>` antes de expirar. El endpoint reutiliza los datos del token vigente para generar uno nuevo con ventana extendida (`jwt_exp_minutes + jwt_refresh_extension_minutes`).

## GitHub

1. `git init`
2. `git add .`
3. `git commit -m "feat: bootstrap FastAPI APIs with AI-assisted services"`
4. Empuja a tu repositorio remoto y documenta en el mensaje de commit qué partes fueron asistidas por IA (por ejemplo, `AI: prompts en app/services/ai.py`).

## Pruebas manuales rápidas

```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"rol":"data_uploader"}'  # especifica el rol requerido

curl -X POST http://localhost:8000/auth/refresh -H "Authorization: Bearer <TOKEN>"
```

Carga de archivo (requiere token y archivo existente):

```bash
curl -X POST http://localhost:8000/files/upload \
  -H "Authorization: Bearer <TOKEN>" \
  -F "param_a=campaña" \
  -F "param_b=lote-1" \
  -F "file=@data.csv"
```

## IA en el proyecto

`AIInsightsService` usa la librería `transformers` para cargar un modelo de resumen local (`google/flan-t5-small` por defecto). En el primer arranque descargará los pesos desde Hugging Face (requiere conexión a Internet). Después funciona completamente sin claves ni costos adicionales. Puedes cambiar el modelo ajustando `AI_MODEL` en `.env`.


