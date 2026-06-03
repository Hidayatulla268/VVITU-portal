import os
from PIL import Image

def inspect_cropped_logo():
    path = "static/images/vvit_logo.png"
    img = Image.open(path).convert('RGBA')
    width, height = img.size
    print(f"Cropped image size: {width}x{height}")
    
    # We will verify that corners are fully transparent (alpha = 0)
    corners = [
        (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)
    ]
    for x, y in corners:
        print(f"Corner ({x}, {y}) alpha: {img.getpixel((x, y))[3]}")
        
    # Check pixels close to center to ensure they are visible (e.g. have alpha = 255 or color)
    center_color = img.getpixel((width // 2, height // 2))
    print(f"Center pixel ({width // 2}, {height // 2}): {center_color}")

if __name__ == "__main__":
    inspect_cropped_logo()
