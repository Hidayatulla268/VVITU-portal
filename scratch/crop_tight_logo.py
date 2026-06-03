import os
import shutil
from PIL import Image, ImageDraw

def crop_tight_logo():
    backup_path = "static/images/vvit_logo_backup.png"
    src_path = "static/images/vvit_logo.png"
    
    if not os.path.exists(backup_path):
        print("Backup file not found! Copying current logo as backup first.")
        shutil.copyfile(src_path, backup_path)
        
    img = Image.open(backup_path).convert('RGBA')
    
    # Crop box for a perfect 240x240 square covering the actual logo emblem
    left = 16
    top = 11
    right = 256
    bottom = 251
    
    size = 240
    print(f"Cropping to: left={left}, top={top}, right={right}, bottom={bottom} (size: {size}x{size})")
    
    cropped = img.crop((left, top, right, bottom))
    
    # Create circular mask
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    
    # Apply circular mask
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(cropped, (0, 0), mask)
    
    # Save back to static/images/vvit_logo.png
    output.save(src_path, 'PNG')
    print(f"Successfully saved cropped circular logo to {src_path}")

if __name__ == "__main__":
    crop_tight_logo()
