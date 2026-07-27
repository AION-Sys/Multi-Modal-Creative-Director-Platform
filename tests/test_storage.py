"""Local object storage round-trips + safety."""

import pytest

from creative_director.storage import LocalStorage, StorageError


async def test_save_load_roundtrip(tmp_path):
    storage = LocalStorage(tmp_path)
    ref = await storage.save("ws1/asset2/v3.png", b"hello-bytes", content_type="image/png")
    assert ref == "local://ws1/asset2/v3.png"
    assert await storage.load(ref) == b"hello-bytes"
    assert await storage.exists(ref) is True


async def test_nested_keys_create_dirs(tmp_path):
    storage = LocalStorage(tmp_path)
    ref = await storage.save("a/b/c/d.bin", b"x")
    assert (tmp_path / "a" / "b" / "c" / "d.bin").read_bytes() == b"x"
    assert await storage.load(ref) == b"x"


async def test_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    ref = await storage.save("f.txt", b"y")
    assert await storage.delete(ref) is True
    assert await storage.exists(ref) is False
    assert await storage.delete(ref) is False


async def test_load_missing_raises(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(StorageError):
        await storage.load("local://nope.png")


async def test_path_traversal_rejected(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(StorageError):
        await storage.save("../escape.txt", b"z")


async def test_foreign_scheme_rejected(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(StorageError):
        await storage.load("s3://bucket/key")
