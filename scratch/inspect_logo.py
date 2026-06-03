import os
from PIL import Image, ImageChops

def inspect_logo():
    path = "static/images/vvit_logo.png"
    if not os.path.exists(path):
        print("Logo not found!")
        return
        
    img = Image.open(path)
    print(f"Format: {img.format}, Size: {img.size}, Mode: {img.mode}")
    
    # If the image has an alpha channel, we can find the bounding box of non-transparent pixels.
    # Otherwise, if it has a white background, we can invert it or check non-white pixels.
    if img.mode != 'RGBA':
        img_rgba = img.convert('RGBA')
    else:
        img_rgba = img

    # Let's find the bounding box of non-white/non-transparent pixels
    # We can define white as any pixel where R, G, B are all > 240 (with alpha > 10)
    width, height = img_rgba.size
    left = width
    top = height
    right = 0
    bottom = 0
    
    # Simple check for bounding box of non-white pixels
    pixels = img_rgba.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # If not white and not transparent
            if a > 10 and not (r > 240 and g > 240 and b > 240):
                if x < left: left = x
                if y < top: top = y
                if x > right: right = x
                if y > bottom: bottom = y
                
    print(f"Bounding box of content (non-white, non-transparent): left={left}, top={top}, right={right}, bottom={bottom}")
    print(f"Content width: {right - left}, Content height: {bottom - top}")

if __name__ == "__main__":
    inspect_logo()
