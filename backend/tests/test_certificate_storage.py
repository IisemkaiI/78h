import pytest

from app.modules.certificates.storage import CertificateStorage


@pytest.mark.asyncio
async def test_private_storage_round_trips_and_rejects_path_traversal(tmp_path) -> None:
    storage = CertificateStorage(tmp_path / "private")
    key = storage.new_key()
    await storage.write(key, b"%PDF-test")

    assert await storage.read(key) == b"%PDF-test"
    assert (tmp_path / "private" / key).is_file()
    with pytest.raises(ValueError):
        await storage.read("..\\public.pdf")


@pytest.mark.asyncio
async def test_private_storage_reports_missing_files(tmp_path) -> None:
    storage = CertificateStorage(tmp_path)
    with pytest.raises(FileNotFoundError):
        await storage.read(storage.new_key())
