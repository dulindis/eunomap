from fastapi import UploadFile
from pathlib import Path
import shutil


# =============================================================================
# File Upload Handling
# =============================================================================
def save_upload(file: UploadFile, note_id: int, upload_dir: Path) -> str:
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"note_{note_id}{ext}"
    file_path = upload_dir / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"static/uploads/{safe_filename}"
