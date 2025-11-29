# app/perception.py
"""
Perception module for Smart Wound-Care Concierge.

analyze_image(pil_img) -> dict with:
{
  "area": int,           # wound-pixel count proxy
  "area_pct": float,     # % of image pixels flagged
  "redness": float,      # mean red channel value in mask or whole image
  "exudate_ratio": float,# ratio of very-bright pixels (proxy for exudate/shine)
  "brightness": float,   # mean grayscale brightness
  "blur_var": float,     # variance of Laplacian (blur detection)
  "mask": np.ndarray     # uint8 mask (0/255) of detected red-ish region
}
""" 

from PIL import Image
import numpy as np
import cv2

def analyze_image(pil_img, target_size=512):
    """
    Analyze an RGB PIL image and return simple wound-related metrics.

    Args:
      pil_img: PIL.Image (RGB)
      target_size: int, max dimension to resize for speed (keeps aspect ratio)

    Returns:
      metrics: dict
    """
    # convert to RGB numpy
    img = np.array(pil_img.convert("RGB"))
    h, w = img.shape[:2]
    # resize to speed up processing while preserving aspect ratio
    max_dim = max(h, w)
    if max_dim > target_size:
        scale = target_size / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # compute basic metrics
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray))
    # blur detection (variance of Laplacian)
    blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # REDNESS detection: proportion of pixels where R is noticeably higher than G & B
    R = img[:, :, 0].astype(np.int32)
    G = img[:, :, 1].astype(np.int32)
    B = img[:, :, 2].astype(np.int32)

    # create red-ish mask heuristics
    # conditions: R substantially > G and B, R above absolute threshold and not too dark
    red_cond = (R > (G * 1.1).astype(np.int32)) & (R > (B * 1.1).astype(np.int32)) & (R > 70)
    # ignore very dark pixels (poor lighting)
    bright_cond = (R + G + B) / 3 > 30
    red_mask = (red_cond & bright_cond).astype(np.uint8) * 255

    # morphology cleaning (open then close)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    total_pixels = red_mask.size
    area = int(np.sum(red_mask > 0))
    area_pct = float(area) / float(total_pixels) * 100.0

    # redness score: mean R value inside mask; fallback to global mean R
    if area > 0:
        redness = float(np.mean(R[red_mask > 0]))
    else:
        redness = float(np.mean(R))

    # exudate proxy: proportion of very bright pixels (specular highlights)
    exudate_ratio = float(np.sum(gray > 230)) / float(total_pixels)

    # package results
    metrics = {
        "area": area,
        "area_pct": area_pct,
        "redness": redness,
        "exudate_ratio": exudate_ratio,
        "brightness": brightness,
        "blur_var": blur_var,
        "mask": red_mask
    }
    return metrics

# If run directly for quick sanity check (not required)
if __name__ == "__main__":
    import sys
    from PIL import Image
    if len(sys.argv) < 2:
        print("Usage: python perception.py PATH_TO_IMAGE")
        sys.exit(1)
    img_path = sys.argv[1]
    pil = Image.open(img_path)
    m = analyze_image(pil)
    print("Metrics:")
    for k, v in m.items():
        if k == "mask":
            print("mask shape:", v.shape, "unique:", np.unique(v)[:5])
        else:
            print(f"  {k}: {v}")
