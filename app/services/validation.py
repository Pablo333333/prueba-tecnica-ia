from collections import Counter


class ValidationService:
    @staticmethod
    def check_missing(rows: list[dict]) -> dict:
        missing_by_row = [
            (idx, [k for k, v in row.items() if v in ("", None)])
            for idx, row in enumerate(rows, start=1)
        ]
        offenders = [(idx, cols) for idx, cols in missing_by_row if cols]
        if not offenders:
            return {"name": "valores_vacios", "status": "OK"}
        detail = "; ".join([f"fila {idx}: {','.join(cols)}" for idx, cols in offenders])
        return {"name": "valores_vacios", "status": "WARN", "details": detail}

    @staticmethod
    def check_duplicates(rows: list[dict]) -> dict:
        serialized = [tuple(sorted(row.items())) for row in rows]
        counts = Counter(serialized)
        duplicates = [row for row, count in counts.items() if count > 1]
        if not duplicates:
            return {"name": "duplicados", "status": "OK"}
        return {"name": "duplicados", "status": "WARN", "details": f"{len(duplicates)} filas repetidas"}

    def run_all(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return [{"name": "contenido", "status": "ERROR", "details": "El archivo está vacío"}]
        return [
            self.check_missing(rows),
            self.check_duplicates(rows),
        ]


def parse_csv(content: str) -> list[dict]:
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO(content))
    return [row for row in reader]

