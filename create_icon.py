import os
from PIL import Image, ImageDraw

def make_round_icon(src_path, output_iconset_name="SikSa.iconset"):
    # Mac Icon Sizes
    sizes = [16, 32, 128, 256, 512]
    
    if not os.path.exists(output_iconset_name):
        os.makedirs(output_iconset_name)
    
    # Open Source
    im = Image.open(src_path).convert("RGBA")
    
    # Crop to square first (center crop)
    w, h = im.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    im = im.crop((left, top, left + min_dim, top + min_dim))
    
    # Process each size
    for s in sizes:
        # 1. Normal (@1x)
        size_1x = (s, s)
        out_1x = im.resize(size_1x, Image.LANCZOS)
        out_1x = apply_mask(out_1x)
        out_1x.save(os.path.join(output_iconset_name, f"icon_{s}x{s}.png"))
        
        # 2. Retina (@2x)
        size_2x = (s*2, s*2)
        out_2x = im.resize(size_2x, Image.LANCZOS)
        out_2x = apply_mask(out_2x)
        out_2x.save(os.path.join(output_iconset_name, f"icon_{s}x{s}@2x.png"))

def apply_mask(img):
    """Apply a rounded rectangle mask (continuous curvature like macOS)"""
    w, h = img.size
    # Radius ~ 22% of total width for macOS squircle approximation
    k = w * 0.22  
    
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw rounded rect
    draw.rounded_rectangle((0, 0, w, h), radius=k, fill=255)
    
    # Composite
    output = Image.new("RGBA", (w, h))
    output.paste(img, (0, 0), mask=mask)
    return output

if __name__ == "__main__":
    src = "/Users/sicks/.gemini/antigravity/brain/6c3ed5f1-3415-4354-991c-940cad173e23/uploaded_image_1765300263781.jpg"
    make_round_icon(src)
    print("Iconset created.")
