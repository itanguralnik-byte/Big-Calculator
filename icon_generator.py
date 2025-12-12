import os
from PIL import Image, ImageDraw, ImageFont

def create_icon(size, filename):
    # Create directory if it doesn't exist
    if not os.path.exists('static/icons'):
        os.makedirs('static/icons')

    # Create a blue background image
    img = Image.new('RGB', (size, size), color='#3b82f6')
    d = ImageDraw.Draw(img)

    # Draw the Sigma symbol
    # Since we might not have a specific font, we draw lines or use default
    # Drawing a simplified Sigma symbol manually using lines
    margin = size * 0.2
    w, h = size, size
    
    points = [
        (w - margin, margin),          # Top Right
        (margin, margin),              # Top Left
        (w * 0.4, h / 2),              # Center Indent
        (margin, h - margin),          # Bottom Left
        (w - margin, h - margin)       # Bottom Right
    ]
    
    d.line(points, fill="white", width=int(size * 0.08), joint="curve")

    # Save
    path = os.path.join('static/icons', filename)
    img.save(path)
    print(f"Generated: {path}")

if __name__ == "__main__":
    create_icon(192, "icon-192.png")
    create_icon(512, "icon-512.png")
    print("Icons created successfully.")