import os
import shutil
from PIL import Image, ImageDraw

def make_logo_circular():
    src_path = "static/images/vvit_logo.png"
    backup_path = "static/images/vvit_logo_backup.png"
    
    # Back up the original logo if not already done
    if not os.path.exists(backup_path):
        shutil.copyfile(src_path, backup_path)
        print(f"Created backup at {backup_path}")
        
    img = Image.open(backup_path).convert('RGBA')
    width, height = img.size
    
    # Determine the crop size (make it a square based on the smaller dimension)
    size = min(width, height) # 265
    
    # Crop to a square centered on the original image
    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size
    
    cropped = img.crop((left, top, right, bottom))
    
    # Create a circular mask
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    
    # Apply the mask to the alpha channel
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(cropped, (0, 0), mask)
    
    # Save the output back to the original path
    output.save(src_path, 'PNG')
    print(f"Saved circular logo to {src_path} with size {size}x{size}")

if __name__ == "__main__":
    make_logo_circular()
