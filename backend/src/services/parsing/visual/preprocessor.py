"""Visual preprocessor: convert .xlsx / .docx pages to PNG snapshots via LibreOffice.

If LibreOffice (`soffice`) is not on PATH, returns an empty list and logs a warning
without raising. Equally if `pdftoppm` or Pillow conversion fails. The orchestrator
treats snapshots as optional context for the VLM.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class PageSnapshot(BaseModel):
    """Single rendered page from LibreOffice."""

    model_config = ConfigDict(extra="ignore")

    page_index: int
    sheet_name: Optional[str] = None
    image_path: str
    width: int = 0
    height: int = 0


class VisualPreprocessor:
    """Convert documents to page snapshots via LibreOffice."""

    def __init__(self, tmp_dir: Optional[str] = None, soffice_cmd: str = "soffice") -> None:
        cm = get_config_manager()
        self._tmp_dir = Path(tmp_dir or cm.get_config("parsing.tmp_dir", "data/tmp/parsing"))
        self._soffice = soffice_cmd

    def is_available(self) -> bool:
        return shutil.which(self._soffice) is not None

    def snapshot(self, file_path: Path) -> List[PageSnapshot]:
        if not self.is_available():
            logger.warning("LibreOffice (soffice) not on PATH; skipping visual preprocessing")
            return []
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"snapshot source missing: {file_path}")
            return []
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="vp_", dir=str(self._tmp_dir)) as work:
            work_path = Path(work)
            pdf_path = self._convert_to_pdf(file_path, work_path)
            if not pdf_path or not pdf_path.exists():
                logger.warning(f"PDF conversion failed for {file_path}")
                return []
            return self._pdf_to_png(pdf_path, work_path, file_path.stem)

    def _convert_to_pdf(self, file_path: Path, work_path: Path) -> Optional[Path]:
        try:
            result = subprocess.run(
                [
                    self._soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(work_path),
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f"soffice failed: {result.stderr.strip()}")
                return None
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning(f"soffice invocation failed: {exc}")
            return None
        return work_path / f"{file_path.stem}.pdf"

    def _pdf_to_png(self, pdf_path: Path, work_path: Path, stem: str) -> List[PageSnapshot]:
        # Prefer pdftoppm when available; otherwise try pypdfium2 / Pillow fallback.
        if shutil.which("pdftoppm"):
            return self._pdftoppm(pdf_path, work_path, stem)
        return self._pillow_pdf(pdf_path, work_path, stem)

    def _pdftoppm(self, pdf_path: Path, work_path: Path, stem: str) -> List[PageSnapshot]:
        prefix = work_path / f"{stem}_page"
        try:
            subprocess.run(
                ["pdftoppm", "-r", "150", "-png", str(pdf_path), str(prefix)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning(f"pdftoppm failed: {exc}")
            return []
        snapshots: List[PageSnapshot] = []
        for idx, png in enumerate(sorted(work_path.glob(f"{stem}_page-*.png"))):
            target = self._tmp_dir / png.name
            shutil.copy(png, target)
            width, height = self._png_size(target)
            snapshots.append(PageSnapshot(page_index=idx, image_path=str(target), width=width, height=height))
        return snapshots

    def _pillow_pdf(self, pdf_path: Path, work_path: Path, stem: str) -> List[PageSnapshot]:
        try:
            import pypdfium2 as pdfium  # type: ignore
        except ImportError:
            logger.warning("Neither pdftoppm nor pypdfium2 available; cannot render PDF to PNG")
            return []
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning(f"pypdfium2 open failed: {exc}")
            return []
        snapshots: List[PageSnapshot] = []
        for idx in range(len(pdf)):
            try:
                page = pdf[idx]
                image = page.render(scale=2.0).to_pil()
                target = self._tmp_dir / f"{stem}_page-{idx + 1:03d}.png"
                image.save(target, format="PNG")
                snapshots.append(
                    PageSnapshot(
                        page_index=idx,
                        image_path=str(target),
                        width=image.width,
                        height=image.height,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - degrade gracefully
                logger.warning(f"page {idx} render failed: {exc}")
        return snapshots

    def _png_size(self, png_path: Path) -> tuple[int, int]:
        try:
            from PIL import Image

            with Image.open(png_path) as img:
                return img.size
        except Exception:  # noqa: BLE001 - best-effort metadata
            return (0, 0)
