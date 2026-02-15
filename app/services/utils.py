import hashlib


async def read_upload_bytes(file):
    return await file.read()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
