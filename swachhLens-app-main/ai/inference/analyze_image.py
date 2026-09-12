"""SwachhLens AI Inference Pipeline.

Two-stage waste detection:
  1. Waste Gate V2 (MobileNetV3-small) — binary waste vs non-waste filter
  2. YOLO Detector (YOLOv11n) — detect specific waste objects

YOLO detections are mapped to the 4 supported waste types:
  Plastic, Organic, E-Waste, Hazardous
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

# ── Model paths ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]
WASTE_GATE_MODEL = BASE_DIR / "models" / "waste_gate_v2_best.pth"
YOLO_MODEL = BASE_DIR / "models" / "waste_types_best.pt"

# ── Thresholds ────────────────────────────────────────────────────────
WASTE_THRESHOLD = 0.40        # Waste Gate: minimum probability to consider waste
YOLO_CONFIDENCE = 0.50        # YOLO: minimum detection confidence

# ── App waste types (the 4 supported categories) ──────────────────────
APP_WASTE_TYPES = ["Plastic", "Organic", "E-Waste", "Hazardous"]

# ── YOLO class name → app waste type mapping ──────────────────────────
# The YOLO model detects 10 fine-grained classes; we map them to the 4
# categories the app supports.
YOLO_TYPE_MAP = {
    # Plastic (recyclables, packaging, bags)
    "recyclable-waste-plastic": "Plastic",
    "recyclable-waste-nylonbag": "Plastic",
    "recyclable-waste-paper": "Plastic",
    "recyclable-waste-paperbag": "Plastic",
    "recyclable-waste-cardboard": "Plastic",
    "recyclable-waste-clothes": "Plastic",
    "recyclable-waste-shoe": "Plastic",
    "recyclable-waste-glass": "Plastic",
    "recyclable-waste-metal": "Plastic",
    # Organic
    "organic-waste": "Organic",
    # E-Waste
    # (no dedicated YOLO class — falls through to Plastic default)
    # Hazardous
    "hazardous-waste": "Hazardous",
    "medical-waste": "Hazardous",
}

DEFAULT_WASTE_TYPE = "Plastic"


# ── Lazy-loaded model singletons ──────────────────────────────────────
_waste_gate = None
_yolo_model = None


def _get_device():
    try:
        import torch
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    except ImportError:
        return None


def _load_waste_gate():
    """Load the Waste Gate V2 model (cached after first call)."""
    global _waste_gate
    if _waste_gate is not None:
        return _waste_gate

    import torch
    from torchvision.models import mobilenet_v3_small

    device = _get_device()
    model = mobilenet_v3_small(weights=None, num_classes=2)

    checkpoint = torch.load(WASTE_GATE_MODEL, map_location=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint

    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    _waste_gate = model
    return model


def _load_yolo():
    """Load the YOLO waste detector (cached after first call)."""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model

    import torch
    torch.serialization.add_safe_globals([])
    from ultralytics import YOLO
    _yolo_model = YOLO(str(YOLO_MODEL))
    return _yolo_model


# ── Transform ─────────────────────────────────────────────────────────
def _get_transform():
    import torch
    from torchvision import transforms
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


# ── Core analysis functions ───────────────────────────────────────────
def _check_waste(model, image, device, transform):
    """Run Waste Gate V2 on the image. Returns (is_waste, waste_prob, non_waste_prob)."""
    import torch

    tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(tensor)
        probs = torch.softmax(output, dim=1)[0]

    waste_prob = probs[1].item()
    non_waste_prob = probs[0].item()
    return waste_prob >= WASTE_THRESHOLD, waste_prob, non_waste_prob


def _detect_waste(yolo, image):
    """Run YOLO detection. Returns (detections, orig_shape)."""
    results = yolo.predict(source=image, conf=YOLO_CONFIDENCE, verbose=False)
    result = results[0]
    detections = []

    if result.boxes is None:
        return detections, result.orig_shape

    for box in result.boxes:
        class_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        xyxy = box.xyxy[0].tolist()
        detections.append({
            "type": result.names[class_id],
            "confidence": confidence,
            "box": xyxy,
        })

    return detections, result.orig_shape


def _map_to_app_type(yolo_type: str) -> str:
    """Map a YOLO class name to one of the 4 supported app waste types."""
    return YOLO_TYPE_MAP.get(yolo_type, DEFAULT_WASTE_TYPE)


def _estimate_severity(detections: list) -> str:
    """Estimate severity from detection count."""
    n = len(detections)
    if n >= 5:
        return "High"
    if n >= 2:
        return "Medium"
    return "Low"


def _non_waste_response(waste_prob: float, reason: str, summary: str) -> dict:
    """Build a consistent NON-WASTE API response."""
    return {
        "valid": False,
        "reason": reason,
        "wasteType": None,
        "severity": None,
        "confidence": 0,
        "engine": "ai",
        "details": [],
        "summary": summary,
    }


def _waste_response(detections: list) -> dict:
    """Build a WASTE-positive API response from confirmed YOLO detections."""
    type_counts: dict[str, int] = {}
    for det in detections:
        app_type = _map_to_app_type(det["type"])
        type_counts[app_type] = type_counts.get(app_type, 0) + 1

    waste_type = max(type_counts, key=type_counts.get)
    highest_conf = max(d["confidence"] for d in detections)
    severity = _estimate_severity(detections)

    details = [
        {"label": _map_to_app_type(d["type"]), "count": 1, "conf": round(d["confidence"] * 100)}
        for d in detections
    ]

    summary = (
        f"{len(detections)} waste item{'s' if len(detections) != 1 else ''} detected. "
        f"Primary type: {waste_type}."
    )

    return {
        "valid": True,
        "reason": None,
        "wasteType": waste_type,
        "severity": severity,
        "confidence": round(highest_conf * 100),
        "engine": "ai",
        "details": details,
        "summary": summary,
    }


# ── Public API ────────────────────────────────────────────────────────
def analyze_image_bytes(image_bytes: bytes) -> dict:
    """Backend entry point: analyze raw image bytes.

    Decision rule:
      1. Waste Gate must consider the image potentially waste (≥ 40%).
      2. YOLO must confirm at least one waste object (≥ 50% confidence).
      3. If YOLO finds nothing → NON-WASTE (scene classifier is NOT used
         as a fallback, to prevent false positives).
    """
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        return _non_waste_response(0, f"Invalid image: {exc}", f"Could not open image: {exc}")

    device = _get_device()
    if device is None:
        # PyTorch not installed — use deterministic demo fallback
        return _demo_analyze(image_bytes)

    transform = _get_transform()

    # ── Step 1: Waste Gate ──
    waste_gate = _load_waste_gate()
    is_waste, waste_prob, non_waste_prob = _check_waste(waste_gate, image, device, transform)

    if not is_waste:
        return _non_waste_response(
            waste_prob,
            "Image does not appear to contain waste.",
            "Image rejected by the waste gate.",
        )

    # ── Step 2: YOLO object confirmation ──
    yolo = _load_yolo()
    detections, _ = _detect_waste(yolo, image)

    if not detections:
        return _non_waste_response(
            waste_prob,
            "No waste object was detected in the image.",
            "The Waste Gate detected possible waste, but YOLO could not confirm a waste object.",
        )

    highest_conf = max(d["confidence"] for d in detections)
    if highest_conf < YOLO_CONFIDENCE:
        return _non_waste_response(
            waste_prob,
            "Waste object confidence is too low.",
            "A possible object was detected, but confidence was too low to confirm waste.",
        )

    return _waste_response(detections)


# ── Demo fallback (when PyTorch is not installed) ─────────────────────
def _demo_analyze(image_bytes: bytes) -> dict:
    """Deterministic demo analysis for environments without PyTorch."""
    import hashlib
    h = int(hashlib.md5(image_bytes[:1024]).hexdigest()[:8], 16)
    wt = APP_WASTE_TYPES[h % len(APP_WASTE_TYPES)]
    sev = ["Low", "Medium", "High"][h % 3]
    conf = 72 + (h % 25)
    return {
        "valid": True,
        "wasteType": wt,
        "severity": sev,
        "confidence": conf,
        "engine": "demo",
        "reason": None,
        "summary": f"AI detected {wt.lower()} waste ({sev.lower()} severity) with {conf}% confidence.",
        "details": [],
    }


# ── CLI entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_image.py <path/to/image.jpg>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: Image not found: {path}")
        sys.exit(1)

    with open(path, "rb") as f:
        result = analyze_image_bytes(f.read())

    print("\n" + "=" * 60)
    print("SWACHHLENS IMAGE ANALYSIS")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60)
