import os
from PIL import Image

def find_logo_bounds():
    path = "static/images/vvit_logo_backup.png"
    if not os.path.exists(path):
        path = "static/images/vvit_logo.png"
        
    img = Image.open(path).convert('RGBA')
    width, height = img.size
    
    # We will find the tightest bounding box of pixels that are NOT black (i.e. not (0, 0, 0, 255) or similar)
    left = width
    top = height
    right = 0
    bottom = 0
    
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # Check if it is NOT close to black (e.g. sum of RGB is > 30) and is visible
            if a > 10 and (r > 15 or g > 15 or b > 15):
                if x < left: left = x
                if y < top: top = y
                if x > right: right = x
                if y > bottom: bottom = y
                
    print(f"Tight bounding box: left={left}, top={top}, right={right}, bottom={bottom}")
    print(f"Content width: {right - left + 1}, height: {bottom - top + 1}")

if __name__ == "__main__":
    find_logo_bounds()
