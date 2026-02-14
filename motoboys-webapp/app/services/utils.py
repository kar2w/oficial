import hashlib
from fastapi import UploadFile


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def read_upload_bytes(file: UploadFile) -> bytes:
    data = await file.read()
    await file.seek(0)
    return data
