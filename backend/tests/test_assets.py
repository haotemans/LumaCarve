import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings


class AssetsTests(unittest.TestCase):
    def test_upload_and_retrieve(self):
        with tempfile.TemporaryDirectory() as temp:
            buf=io.BytesIO()
            Image.new("RGB",(16,12),"purple").save(buf,format="PNG")
            raw=buf.getvalue()
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as c:
                res=c.post("/api/v1/assets",files={"file":("image.png",raw,"image/png")})
                self.assertEqual(res.status_code,201,res.text)
                self.assertEqual(res.json()["id"],hashlib.sha256(raw).hexdigest())
                self.assertEqual(res.json()["width"],16)
                self.assertEqual(c.get("/api/v1/assets/"+res.json()["id"]).content,raw)
                self.assertEqual(c.post("/api/v1/assets",files={"file":("image.png",raw,"image/png")}).status_code,201)

    def test_nonimage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as c:
                r=c.post("/api/v1/assets",files={"file":("bad.png",b"not an image","image/png")})
                self.assertEqual(r.status_code,422)
                self.assertEqual(c.get("/api/v1/assets/notanid").status_code,400)

    def test_upload_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            settings=Settings(data_dir=Path(temp),max_asset_bytes=1024)
            with TestClient(create_app(settings)) as c:
                r=c.post("/api/v1/assets",files={"file":("big.bin",b"a"*2048,"application/octet-stream")})
                self.assertEqual(r.status_code,422)


if __name__ == "__main__":
    unittest.main()
