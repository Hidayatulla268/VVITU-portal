import os
from PIL import Image

def make_logo_transparent_square():
    backup_path = "static/images/vvit_logo_backup.png"
    src_path = "static/images/vvit_logo.png"
    
    if not os.path.exists(backup_path):
        print("Backup file not found!")
        return
        
    img = Image.open(backup_path).convert('RGBA')
    width, height = img.size
    
    # Bounding box of emblem was left=16, top=11, right=256, bottom=251
    # Crop to a square of 240x240
    left = 16
    top = 11
    right = 256
    bottom = 251
    size = 240
    
    cropped = img.crop((left, top, right, bottom))
    
    # Let's make any black pixels transparent
    # We load pixels of the cropped image
    pixels = cropped.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = pixels[x, y]
            # If it is black or very dark (sum of RGB < 45)
            if r < 18 and g < 18 and b < 18:
                pixels[x, y] = (0, 0, 0, 0)
                
    # Save the transparent square logo
    cropped.save(src_path, 'PNG')
    print(f"Saved transparent square logo to {src_path}")

if __name__ == "__main__":
    make_logo_transparent_square()
