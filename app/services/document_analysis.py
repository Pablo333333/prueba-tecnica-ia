import re
from dataclasses import dataclass
from io import BytesIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from functools import lru_cache
from pypdf import PdfReader
from transformers import pipeline

from app.core.config import settings
from app.models.document import DocumentAnalysis
from app.schemas.documents import DocumentAnalysisResult, FacturaData, InformacionData, ProductoItem
from app.services.interfaces import (
    DocumentClassifierProtocol,
    DocumentRepositoryProtocol,
    InformationAnalyzerProtocol,
    InvoiceParserProtocol,
    StorageServiceProtocol,
    TextExtractorProtocol,
)
from app.services.storage import S3StorageService


@dataclass
class AnalyzerResult:
    """Representa el registro almacenado y el payload de respuesta."""

    record: DocumentAnalysis
    payload: DocumentAnalysisResult


class DocumentTextExtractor:
    """Extrae texto plano desde PDFs o imágenes usando Textract."""

    def __init__(self, textract_client=None):
        self.textract = textract_client or self._build_textract_client()

    def extract(self, filename: str, content: bytes) -> str:
        """
        Obtiene el texto del archivo recibido y devuelve una versión saneada.

        Args:
            filename (str): Nombre del archivo para detectar su tipo.
            content (bytes): Bytes crudos del documento.

        Returns:
            str: Texto normalizado en UTF-8 sin caracteres de control.
        """
        if filename.lower().endswith(".pdf"):
            raw_text = self._extract_pdf(content)
        else:
            raw_text = self._extract_image(content)
        return self._sanitize(raw_text)

    @staticmethod
    def _build_textract_client():
        """Crea el cliente de Textract con las credenciales configuradas."""
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        return session.client("textract")

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        """Lee un PDF con PyPDF e integra sus páginas."""
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_image(self, content: bytes) -> str:
        """Ejecuta Textract (o fallback) para imágenes."""
        try:
            response = self.textract.detect_document_text(Document={"Bytes": content})
            return " ".join(
                item["DetectedText"] for item in response.get("Blocks", []) if item["BlockType"] == "LINE"
            )
        except (ClientError, BotoCoreError):
            return content.decode("utf-8", errors="ignore")

    @staticmethod
    def _sanitize(text: str) -> str:
        """Limpia caracteres de control y reduce espacios consecutivos."""
        clean = text.replace("\x00", " ")
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:10000]


class DocumentClassifier:
    """Determina si el texto corresponde a una factura o información general."""

    KEYWORDS = ["factura", "invoice", "subtotal", "iva", "total"]

    def classify(self, text: str) -> str:
        """
        Aplica un conteo de palabras clave para etiquetar el documento.

        Args:
            text (str): Texto plano extraído del archivo.

        Returns:
            str: "FACTURA" cuando hay suficientes palabras clave, "INFORMACION" en caso contrario.
        """
        score = sum(1 for word in self.KEYWORDS if word in text.lower())
        return "FACTURA" if score >= 2 else "INFORMACION"


class InvoiceParser:
    """Convierte el texto de una factura en un objeto FacturaData."""

    def parse(self, text: str) -> FacturaData:
        """
        Localiza clientes, totales, fechas y productos dentro del texto plano.

        Args:
            text (str): Texto completo del documento.

        Returns:
            FacturaData: Datos estructurados de la factura.
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

    @staticmethod
    def _extract_party_block(text: str, label: str):
        """Extrae nombre y dirección asociados a la etiqueta dada."""
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
        return InvoiceParser._normalize_amount(matches[-1])

    def _extract_products(self, text: str):
        """
        Construye los ProductoItem encontrados en la sección tabular.

        Args:
            text (str): Texto donde se ubica la tabla.

        Returns:
            list[ProductoItem]: Lista de productos detectados.
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


class InformationAnalyzer:
    """Genera resumen y sentimiento para documentos de texto general."""

    def __init__(self, summary_pipeline=None, sentiment_pipeline=None):
        self.summary_pipeline = summary_pipeline or get_summary_pipeline()
        self.sentiment_pipeline = sentiment_pipeline or get_sentiment_pipeline()

    def analyze(self, text: str) -> InformacionData:
        """
        Construye un resumen corto y detecta sentimiento del texto.

        Args:
            text (str): Contenido completo del documento.

        Returns:
            InformacionData: Modelo con descripción, resumen y sentimiento.
        """
        descripcion = text[:400]
        resumen = self._build_summary(descripcion)
        sentimiento = self._detect_sentiment(descripcion)
        return InformacionData(descripcion=descripcion, resumen=resumen, sentimiento=sentimiento)

    def _build_summary(self, descripcion: str) -> str:
        """Genera el resumen usando el pipeline configurado."""
        if not descripcion.strip():
            return ""
        result = self.summary_pipeline(descripcion, max_length=80)
        return result[0]["generated_text"]

    def _detect_sentiment(self, descripcion: str) -> str:
        """Mapea el sentimiento del texto a positivo/negativo/neutral."""
        if not descripcion.strip():
            return "neutral"
        sentiment_raw = self.sentiment_pipeline(descripcion[:512])[0]["label"]
        sentiment_map = {"POSITIVE": "positivo", "NEGATIVE": "negativo"}
        return sentiment_map.get(sentiment_raw.upper(), "neutral")


class DocumentAnalyzerService:
    """Coordina extracción, parsing y persistencia del análisis de documentos."""

    def __init__(
        self,
        repository: DocumentRepositoryProtocol,
        *,
        storage_service: StorageServiceProtocol | None = None,
        text_extractor: TextExtractorProtocol | None = None,
        classifier: DocumentClassifierProtocol | None = None,
        invoice_parser: InvoiceParserProtocol | None = None,
        info_analyzer: InformationAnalyzerProtocol | None = None,
    ):
        """
        Configura las dependencias necesarias para procesar documentos.

        Args:
            repository (DocumentRepositoryProtocol): Encargado de persistir resultados.
            storage_service (StorageServiceProtocol | None): Servicio para subir archivos.
            text_extractor (TextExtractorProtocol | None): Obtiene texto plano del archivo.
            classifier (DocumentClassifierProtocol | None): Determina el tipo del documento.
            invoice_parser (InvoiceParserProtocol | None): Convierte facturas a datos estructurados.
            info_analyzer (InformationAnalyzerProtocol | None): Resume documentos informativos.
        """
        self.repository = repository
        self.storage_service = storage_service or S3StorageService()
        self.text_extractor = text_extractor or DocumentTextExtractor()
        self.classifier = classifier or DocumentClassifier()
        self.invoice_parser = invoice_parser or InvoiceParser()
        self.info_analyzer = info_analyzer or InformationAnalyzer()

    def analyze(self, *, filename: str, content: bytes) -> AnalyzerResult:
        """
        Ejecuta todo el flujo de análisis y persiste el resultado final.

        Args:
            filename (str): Nombre original del archivo.
            content (bytes): Bytes recibidos durante la carga.

        Returns:
            AnalyzerResult: Estructura con el registro ORM y el payload de respuesta.
        """
        text_content = self.text_extractor.extract(filename, content)
        document_type = self.classifier.classify(text_content)

        if document_type == "FACTURA":
            parsed = self.invoice_parser.parse(text_content)
            info = DocumentAnalysisResult(
                document_type=document_type,
                factura=parsed,
                informacion=None,
                raw_text=text_content,
            )
            sentiment = None
            summary = parsed.total and f"Factura con total estimado {parsed.total}"
        else:
            parsed = self.info_analyzer.analyze(text_content)
            info = DocumentAnalysisResult(
                document_type=document_type,
                factura=None,
                informacion=parsed,
                raw_text=text_content,
            )
            sentiment = parsed.sentimiento
            summary = parsed.resumen

        try:
            s3_key = self.storage_service.upload(content=content, filename=filename, prefix="documents")
        except RuntimeError:
            s3_key = None

        record = self.repository.save_analysis(
            filename=filename,
            document_type=document_type,
            s3_key=s3_key,
            payload=info,
            ai_summary=summary,
            sentiment=sentiment,
        )

        return AnalyzerResult(record=record, payload=info)


@lru_cache(maxsize=1)
def get_summary_pipeline():
    """Carga una vez el pipeline de resumen y lo reutiliza."""
    return pipeline("text2text-generation", model=settings.ai_model)


@lru_cache(maxsize=1)
def get_sentiment_pipeline():
    """Carga una vez el pipeline de sentimiento y lo reutiliza."""
    return pipeline("sentiment-analysis", model=settings.sentiment_model)

