#!/usr/bin/env python3
"""
Generate application icons using Pillow

Creates PNG icons at various sizes and macOS .icns file.
"""

import subprocess
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw


def create_icon_image(size: int) -> Image.Image:
    """Create the CameoCut icon programmatically"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate scale factor
    scale = size / 512

    # Background rounded rectangle
    margin = int(32 * scale)
    corner_radius = int(64 * scale)

    # Draw rounded rectangle background (blue gradient approximation)
    for i in range(int(448 * scale)):
        # Gradient from #2196F3 to #1565C0
        ratio = i / (448 * scale)
        r = int(33 + (21 - 33) * ratio)
        g = int(150 + (101 - 150) * ratio)
        b = int(243 + (192 - 243) * ratio)
        color = (r, g, b, 255)

        y = margin + i
        x1 = margin
        x2 = size - margin

        if i < corner_radius:
            # Top corners
            offset = corner_radius - int((corner_radius**2 - (corner_radius - i)**2)**0.5)
            x1 = margin + offset
            x2 = size - margin - offset
        elif i > int(448 * scale) - corner_radius:
            # Bottom corners
            from_bottom = int(448 * scale) - i
            offset = corner_radius - int((corner_radius**2 - (corner_radius - from_bottom)**2)**0.5)
            x1 = margin + offset
            x2 = size - margin - offset

        draw.line([(x1, y), (x2, y)], fill=color)

    # Grid lines (subtle)
    grid_color = (255, 255, 255, 40)
    line_width = max(1, int(2 * scale))

    # Vertical grid lines
    for x_base in [128, 224, 320, 416]:
        x = int(x_base * scale)
        draw.line([(x, int(80 * scale)), (x, int(432 * scale))], fill=grid_color, width=line_width)

    # Horizontal grid lines
    for y_base in [128, 224, 320, 416]:
        y = int(y_base * scale)
        draw.line([(int(80 * scale), y), (int(432 * scale), y)], fill=grid_color, width=line_width)

    # Star cut path (yellow)
    star_points = [
        (256, 120), (290, 200), (380, 200), (310, 260), (335, 350),
        (256, 300), (177, 350), (202, 260), (132, 200), (222, 200)
    ]
    scaled_star = [(int(x * scale), int(y * scale)) for x, y in star_points]
    star_color = (255, 235, 59, 255)
    line_width = max(2, int(8 * scale))

    # Draw star outline
    for i in range(len(scaled_star)):
        p1 = scaled_star[i]
        p2 = scaled_star[(i + 1) % len(scaled_star)]
        draw.line([p1, p2], fill=star_color, width=line_width)

    # Cutter blade (simplified)
    blade_x = int(360 * scale)
    blade_y = int(160 * scale)
    blade_size = int(40 * scale)

    # Blade holder (dark gray rectangle)
    holder_color = (66, 66, 66, 255)
    holder_w = int(20 * scale)
    holder_h = int(45 * scale)
    draw.rectangle([
        (blade_x - holder_w//2, blade_y - holder_h),
        (blade_x + holder_w//2, blade_y)
    ], fill=holder_color)

    # Blade tip (triangle, silver)
    blade_color = (200, 200, 200, 255)
    tip_points = [
        (blade_x, blade_y + int(18 * scale)),
        (blade_x - int(8 * scale), blade_y),
        (blade_x + int(8 * scale), blade_y)
    ]
    draw.polygon(tip_points, fill=blade_color)

    # Grip rings
    ring_color = (97, 97, 97, 255)
    ring_h = int(4 * scale)
    for offset in [int(50 * scale), int(40 * scale)]:
        draw.rectangle([
            (blade_x - holder_w//2 - 2, blade_y - offset),
            (blade_x + holder_w//2 + 2, blade_y - offset + ring_h)
        ], fill=ring_color)

    # DXF badge
    badge_x = int(80 * scale)
    badge_y = int(380 * scale)
    badge_w = int(80 * scale)
    badge_h = int(36 * scale)
    badge_r = int(8 * scale)

    draw.rounded_rectangle([
        (badge_x, badge_y),
        (badge_x + badge_w, badge_y + badge_h)
    ], radius=badge_r, fill=(255, 255, 255, 255))

    # DXF text (simplified - just a rectangle for small sizes)
    if size >= 64:
        try:
            from PIL import ImageFont
            font_size = int(18 * scale)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()

            text = "DXF"
            text_color = (21, 101, 192, 255)

            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            text_x = badge_x + (badge_w - text_w) // 2
            text_y = badge_y + (badge_h - text_h) // 2 - int(2 * scale)

            draw.text((text_x, text_y), text, fill=text_color, font=font)
        except:
            pass  # Skip text for very small sizes or if font fails

    return img


def generate_icons():
    """Generate PNG icons at various sizes"""
    base_dir = Path(__file__).parent.parent
    icons_dir = base_dir / "resources" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Icon sizes needed for various platforms
    sizes = [16, 32, 48, 64, 128, 256, 512, 1024]

    print("Generating PNG icons...")
    for size in sizes:
        output_path = icons_dir / f"cameocut_{size}.png"
        img = create_icon_image(size)
        img.save(output_path, "PNG")
        print(f"  Created: {output_path.name}")

    # Create main icon (512x512)
    main_icon = icons_dir / "cameocut.png"
    img = create_icon_image(512)
    img.save(main_icon, "PNG")
    print(f"  Created: {main_icon.name}")

    # Generate macOS .icns file
    generate_icns(icons_dir)


def generate_icns(icons_dir: Path):
    """Generate macOS .icns file using iconutil"""
    iconset_dir = icons_dir / "cameocut.iconset"
    iconset_dir.mkdir(exist_ok=True)

    # macOS iconset requires specific naming
    icon_specs = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    print("\nCreating iconset...")
    for size, name in icon_specs:
        src = icons_dir / f"cameocut_{size}.png"
        dst = iconset_dir / name
        if src.exists():
            shutil.copy(src, dst)
            print(f"  {name}")

    # Convert iconset to icns
    icns_path = icons_dir / "cameocut.icns"
    print(f"\nGenerating {icns_path.name}...")

    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True
        )
        print(f"  Created: {icns_path.name}")
    except FileNotFoundError:
        print("  iconutil not found (macOS only)")
    except subprocess.CalledProcessError as e:
        print(f"  Failed to create icns: {e}")

    # Cleanup iconset directory
    shutil.rmtree(iconset_dir, ignore_errors=True)


if __name__ == "__main__":
    generate_icons()
    print("\nDone!")
