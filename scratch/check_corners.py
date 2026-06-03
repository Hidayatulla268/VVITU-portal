import os
from PIL import Image

def check_corners():
    path = "static/images/vvit_logo_backup.png"
    if not os.path.exists(path):
        path = "static/images/vvit_logo.png"
        
    img = Image.open(path).convert('RGBA')
    width, height = img.size
    print(f"Size: {width}x{height}")
    
    # Check pixels at corners and edges
    corners = [
        (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
        (width // 2, 0), (width // 2, height - 1), (0, height // 2), (width - 1, height // 2)
    ]
    for x, y in corners:
        print(f"Pixel ({x}, {y}): {img.getpixel((x, y))}")

if __name__ == "__main__":
    check_corners()
