import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pypdf import PdfReader
from functools import lru_cache
from transformers import pipeline

from app.core.config import settings
from app.models.document import DocumentAnalysis
from app.schemas.documents import DocumentAnalysisResult, FacturaData, InformacionData, ProductoItem
from app.services.storage import S3StorageService


@dataclass
class AnalyzerResult:
    record: DocumentAnalysis
    payload: DocumentAnalysisResult


class DocumentAnalyzerService:
    """Servicio que centraliza la subida a S3, el uso de Textract y los aportes de IA."""

    def __init__(self, db):
        """
        Inicializa el analizador con las dependencias de base de datos y AWS/Textract.

        Args:
            db (Session): Sesión activa de SQLAlchemy utilizada para almacenar el resultado del análisis.
        """
        self.db = db
        self.s3_service = S3StorageService()
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.textract = session.client("textract")
        self.summary_pipeline = get_summary_pipeline()
        self.sentiment_pipeline = get_sentiment_pipeline()

    def analyze(self, *, filename: str, content: bytes) -> AnalyzerResult:
        """
        Clasifica, extrae y persiste el análisis de un documento binario.

        Args:
            filename (str): Nombre original del archivo cargado.
            content (bytes): Datos crudos del archivo recibidos en la carga multipart.

        Returns:
            AnalyzerResult: Contenedor con el registro ORM y el payload de respuesta.
        """
        text_content = self._sanitize_text(self._extract_text(filename, content))
        document_type = self._classify_text(text_content)

        if document_type == "FACTURA":
            parsed = self._extract_invoice(text_content)
            info = DocumentAnalysisResult(
                document_type=document_type,
                factura=parsed,
                informacion=None,
                raw_text=text_content,
            )
            sentiment = None
            summary = parsed.total and f"Factura con total estimado {parsed.total}"
        else:
            parsed = self._extract_information(text_content)
            info = DocumentAnalysisResult(
                document_type=document_type,
                factura=None,
                informacion=parsed,
                raw_text=text_content,
            )
            sentiment = parsed.sentimiento
            summary = parsed.resumen

        s3_key = self._upload_document(filename, content)

        record = DocumentAnalysis(
            filename=filename,
            document_type=document_type,
            s3_key=s3_key,
            extracted_payload=json.dumps(info.dict(), ensure_ascii=False),
            ai_summary=summary,
            sentiment=sentiment,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return AnalyzerResult(record=record, payload=info)

    def _upload_document(self, filename: str, content: bytes) -> str | None:
        """
        Sube el archivo binario a S3 y devuelve la clave del objeto.

        Args:
            filename (str): Nombre original, usado para conservar la extensión en S3.
            content (bytes): Bytes que se enviarán al almacenamiento.

        Returns:
            str | None: Clave del objeto generado si la subida tiene éxito, None en caso contrario.
        """
        if not content:
            return None
        key = f"documents/{uuid.uuid4()}/{filename}"
        try:
            self.s3_service.client.put_object(Bucket=self.s3_service.bucket, Key=key, Body=content)
            return key
        except (ClientError, BotoCoreError):
            return None

    def _extract_text(self, filename: str, content: bytes) -> str:
        """
        Extrae el contenido textual de un PDF o imagen usando Textract o lectura directa.

        Args:
            filename (str): Nombre del archivo para distinguir PDFs de imágenes.
            content (bytes): Contenido binario completo del archivo.

        Returns:
            str: Texto en UTF-8 obtenido de la mejor forma posible.
        """
        if filename.lower().endswith(".pdf"):
            import io

            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        try:
            response = self.textract.detect_document_text(Document={"Bytes": content})
            return " ".join(
                [item["DetectedText"] for item in response.get("Blocks", []) if item["BlockType"] == "LINE"]
            )
        except (ClientError, BotoCoreError):
            return content.decode("utf-8", errors="ignore")

    def _classify_text(self, text: str) -> str:
        """
        Determina si el documento se asemeja a una factura o a información general.

        Args:
            text (str): Texto plano extraído del documento.

        Returns:
            str: "FACTURA" cuando se detectan palabras clave, de lo contrario "INFORMACION".
        """
        keywords = ["factura", "invoice", "subtotal", "iva", "total"]
        score = sum(1 for word in keywords if word in text.lower())
        return "FACTURA" if score >= 2 else "INFORMACION"

    def _extract_invoice(self, text: str) -> FacturaData:
        """
        Interpreta el texto de una factura y lo transforma en campos estructurados.

        Args:
            text (str): Texto plano con metadatos y tablas típicas de una factura.

        Returns:
            FacturaData: Modelo con cliente, proveedor, productos y totales identificados.
        """
        cliente = self._extract_party_block(text, "cliente")
        proveedor = self._extract_party_block(text, "proveedor")
        numero = self._extract_field(
            text, r"(?:número\s+de\s+factura|invoice\s+number)\s*[:\-\s]+([A-Z0-9\-]+)"
        )
        fecha = self._extract_field(
            text, r"(?:fecha|date)\s*[:\-\s]+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
        )
        total = self._extract_amount(
            text, r"(?:total\s+de\s+la\s+factura|importe\s+total|total)\s*[:\-\s]+\$?([\d.,]+)"
        )
        productos = self._extract_products(text)
        return FacturaData(
            cliente=cliente,
            proveedor=proveedor,
            numero=numero,
            fecha=fecha,
            total=total,
            productos=productos,
        )

    def _extract_information(self, text: str) -> InformacionData:
        """
        Genera un resumen y sentimiento para un documento no clasificado como factura.

        Args:
            text (str): Texto completo extraído del documento.

        Returns:
            InformacionData: Estructura con descripción, resumen y etiqueta de sentimiento.
        """
        descripcion = text[:400]
        summary = self.summary_pipeline(descripcion, max_length=80)[0]["generated_text"]
        sentiment_raw = self.sentiment_pipeline(descripcion[:512])[0]["label"]
        sentiment_map = {"POSITIVE": "positivo", "NEGATIVE": "negativo"}
        sentimiento = sentiment_map.get(sentiment_raw.upper(), "neutral")
        return InformacionData(descripcion=descripcion, resumen=summary, sentimiento=sentimiento)

    @staticmethod
    def _extract_party_block(text: str, label: str):
        """
        Extrae el bloque de nombre y dirección correspondiente al label solicitado.

        Args:
            text (str): Representación textual completa del documento.
            label (str): Palabra clave a buscar, habitualmente "cliente" o "proveedor".

        Returns:
            dict | None: Diccionario con las claves "nombre" y "direccion" o None si no se encuentra.
        """
        pattern = re.compile(
            rf"{label}\s*:\s*(.+?)(?=(?:cliente|proveedor|número\s+de\s+factura|numero\s+de\s+factura|número|numero|invoice\s+number|fecha|cantidad|total|descripción|descripcion|$))",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            return None
        block = re.sub(r"\s+", " ", match.group(1)).strip(" ,:")
        cut_keywords = [
            r"\bAv\.?\b",
            r"\bAvenida\b",
            r"\bCalle\b",
            r"\bCarrera\b",
            r"\bCl\.?\b",
            r"\bRuta\b",
            r"\bBoulevard\b",
            r"\d+\w*",
        ]
        split_index = None
        for kw in cut_keywords:
            kw_match = re.search(kw, block, re.IGNORECASE)
            if kw_match:
                split_index = kw_match.start()
                break
        if split_index is None and "," in block:
            split_index = block.index(",")
        if split_index is not None:
            nombre = block[:split_index].strip(" ,")
            direccion = block[split_index:].strip(" ,")
        else:
            nombre = block
            direccion = None
        return {"nombre": nombre or None, "direccion": direccion or None}

    @staticmethod
    def _extract_field(text: str, pattern: str):
        """Devuelve la coincidencia de un patrón regex limpio o None."""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_amount(text: str, pattern: str):
        """Obtiene un monto del texto y lo normaliza a float."""
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            return None
        return DocumentAnalyzerService._normalize_amount(matches[-1])

    def _extract_products(self, text: str):
        """
        Analiza la sección tabular de la factura y genera objetos ProductoItem.

        Args:
            text (str): Texto completo de la factura utilizado para ubicar la tabla.

        Returns:
            list[ProductoItem]: Lista de productos con cantidad, descripción y valores numéricos.
        """
        productos: list[ProductoItem] = []
        table_match = re.search(
            r"Cantidad\s+Producto.*?Total(.*?)(?:Total\s+de\s+la\s+factura|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        table_body = table_match.group(1) if table_match else text
        pattern = re.compile(
            r"(\d+)\s+([A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ\-\.\s]+)\s+\$?([\d.,]+)\s+\$?([\d.,]+)"
        )
        for qty, name, price, total in pattern.findall(table_body):
            productos.append(
                ProductoItem(
                    cantidad=float(qty),
                    nombre=name.strip(),
                    precio_unitario=self._normalize_amount(price),
                    total=self._normalize_amount(total),
                )
            )
        return productos

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Quita caracteres de control y limita el texto a 10k caracteres."""
        clean = text.replace("\x00", " ")
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:10000]

    @staticmethod
    def _normalize_amount(value: str | None) -> float | None:
        """Convierte un string con formato monetario en float (o None)."""
        if not value:
            return None
        cleaned = value.replace("$", "").replace(" ", "")
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            cleaned = cleaned.replace(".", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None


@lru_cache(maxsize=1)
def get_summary_pipeline():
    """Carga una vez el pipeline de resumen y lo reutiliza."""
    return pipeline("text2text-generation", model=settings.ai_model)


@lru_cache(maxsize=1)
def get_sentiment_pipeline():
    """Carga una vez el pipeline de sentimiento y lo reutiliza."""
    return pipeline("sentiment-analysis")

