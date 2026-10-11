"""Extra adapters: mediapipe, rapidocr, pycaption, opencolorio.

Same rules: lazy imports, no installs/downloads inside adapters (model
files are explicit contract inputs, acquired by the caller with recorded
provenance — see tests for the pinned URLs used in validation).
"""
from __future__ import annotations

from pathlib import Path

from .base import ExecutionAdapter, ToolUnavailable
from .providers import ADAPTERS, _have


class MediaPipeAdapter(ExecutionAdapter):
    provider_id = "mediapipe"
    capabilities = ("FACE_LANDMARKS", "HAND_POSE")

    def available(self):
        return (_have("mediapipe"), "ok" if _have("mediapipe")
                else "mediapipe missing")

    def run(self, contract):
        self._require()
        import cv2
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        model = Path(contract["model"])
        if not model.is_file():
            raise ToolUnavailable(self.provider_id,
                                  f"task model missing: {model}")
        base = mp_python.BaseOptions(model_asset_path=str(model))
        opts = vision.FaceLandmarkerOptions(
            base_options=base, num_faces=int(contract.get("num_faces", 3)))
        img = cv2.imread(contract["src"])
        if img is None:
            raise ToolUnavailable(self.provider_id, "unreadable image")
        mp_img = __import__("mediapipe").Image(
            image_format=__import__("mediapipe").ImageFormat.SRGB,
            data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        with vision.FaceLandmarker.create_from_options(opts) as det:
            res = det.detect(mp_img)
        faces = [{"landmarks": len(f)} for f in res.face_landmarks]
        return self.artifact("faces", contract["src"], self.provider_id,
                             count=len(faces))


class RapidOcrAdapter(ExecutionAdapter):
    provider_id = "rapidocr"
    capabilities = ("OCR", "SCREEN_TEXT")

    def available(self):
        return (_have("rapidocr_onnxruntime"),
                "ok" if _have("rapidocr_onnxruntime")
                else "rapidocr_onnxruntime missing")

    def run(self, contract):
        self._require()
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        result, _ = engine(contract["src"])
        boxes = [{"box": [[round(float(v), 1) for v in pt] for pt in b],
                  "text": t, "conf": round(float(c), 3)}
                 for b, t, c in (result or [])]
        return self.artifact("ocr", contract["src"], self.provider_id,
                             boxes=len(boxes),
                             texts=[b["text"] for b in boxes])


class PycaptionAdapter(ExecutionAdapter):
    provider_id = "pycaption"
    capabilities = ("SUBTITLE_CONVERT",)

    def available(self):
        return (_have("pycaption"), "ok" if _have("pycaption")
                else "pycaption missing")

    def run(self, contract):
        self._require()
        from pycaption import SRTReader, WebVTTWriter
        caps = SRTReader().read(contract["srt_text"])
        out = WebVTTWriter().write(caps)
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(out, encoding="utf-8")
        langs = caps.get_languages()
        total = sum(len(caps.get_captions(lang)) for lang in langs)
        return self.artifact("vtt", dst, self.provider_id, cues=total)


class OcioAdapter(ExecutionAdapter):
    provider_id = "opencolorio"
    capabilities = ("COLOR_TRANSFORM",)

    def available(self):
        return (_have("PyOpenColorIO"), "ok" if _have("PyOpenColorIO")
                else "PyOpenColorIO missing")

    def run(self, contract):
        self._require()
        import numpy as np
        import PyOpenColorIO as ocio
        arr = np.asarray(contract["pixels"], dtype=np.float32)
        gain = float(contract.get("exposure_mult", 2.0))
        mat = ocio.MatrixTransform()
        mat.setMatrix([gain, 0.0, 0.0, 0.0,
                       0.0, gain, 0.0, 0.0,
                       0.0, 0.0, gain, 0.0,
                       0.0, 0.0, 0.0, 1.0])
        proc = ocio.Config().getProcessor(mat).getDefaultCPUProcessor()
        mean_in = round(float(arr.mean()), 4)
        flat = np.ascontiguousarray(arr.reshape(-1, 3))
        proc.applyRGB(flat)
        out = flat.reshape(arr.shape)
        return self.artifact("pixels", "inline", self.provider_id,
                             mean_in=mean_in,
                             mean_out=round(float(out.mean()), 4))


for _cls in (MediaPipeAdapter, RapidOcrAdapter, PycaptionAdapter,
             OcioAdapter):
    ADAPTERS[_cls.provider_id] = _cls()
