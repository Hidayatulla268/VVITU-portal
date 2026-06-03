import os
import math
from PIL import Image

def analyze_circle():
    path = "static/images/vvit_logo.png"
    img = Image.open(path).convert('RGBA')
    width, height = img.size
    cx, cy = width / 2.0, height / 2.0
    
    # Let's scan along several angles to find the transition from logo content to white background
    # We will check angles from 0 to 360 degrees
    edge_distances = []
    for angle_deg in range(0, 360, 10):
        angle = math.radians(angle_deg)
        dx = math.cos(angle)
        dy = math.sin(angle)
        
        # Scan from center outwards
        max_dist = min(width, height)
        found_edge = None
        for d in range(int(max_dist)):
            x = int(cx + dx * d)
            y = int(cy + dy * d)
            if x < 0 or x >= width or y < 0 or y >= height:
                found_edge = d
                break
            r, g, b, a = img.getpixel((x, y))
            # If we hit solid white or transparent
            if a < 10 or (r > 240 and g > 240 and b > 240):
                # Let's see if all remaining pixels to the edge are also white/transparent
                all_white = True
                for test_d in range(d, int(max_dist)):
                    tx = int(cx + dx * test_d)
                    ty = int(cy + dy * test_d)
                    if 0 <= tx < width and 0 <= ty < height:
                        tr, tg, tb, ta = img.getpixel((tx, ty))
                        if ta >= 10 and not (tr > 240 and tg > 240 and tb > 240):
                            all_white = False
                            break
                if all_white:
                    found_edge = d
                    break
        if found_edge is not None:
            edge_distances.append(found_edge)
            
    print(f"Detected edge distances: {edge_distances}")
    if edge_distances:
        avg_r = sum(edge_distances) / len(edge_distances)
        min_r = min(edge_distances)
        max_r = max(edge_distances)
        print(f"Average radius of logo content: {avg_r:.1f}")
        print(f"Min radius: {min_r}, Max radius: {max_r}")
        
if __name__ == "__main__":
    analyze_circle()
