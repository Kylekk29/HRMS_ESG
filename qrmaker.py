import qrcode
from PIL import Image
import os

def generate_qr_with_icon(data, icon_path, output_path, qr_size=10, icon_size_ratio=0.2):
    """
    Generate a QR code with an icon in the center
    
    Args:
        data (str): Data to encode in the QR code
        icon_path (str): Path to the icon image file
        output_path (str): Path to save the output QR code
        qr_size (int): Size of QR code (1-40, default 10)
        icon_size_ratio (float): Ratio of icon size to QR code size (default 0.25)
    """
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=qr_size,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for icon
        box_size=10,
        border=4,
    )
    
    # Add data to QR code
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create QR code image
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Load the icon
    try:
        icon = Image.open(icon_path)
    except FileNotFoundError:
        print(f"Error: Icon file not found at {icon_path}")
        return
    
    # Calculate icon size (percentage of QR code size)
    qr_width, qr_height = qr_img.size
    icon_size = int(min(qr_width, qr_height) * icon_size_ratio)
    
    # Resize icon while maintaining aspect ratio
    icon_width, icon_height = icon.size
    aspect_ratio = icon_width / icon_height
    
    if icon_width > icon_height:
        new_width = icon_size
        new_height = int(icon_size / aspect_ratio)
    else:
        new_height = icon_size
        new_width = int(icon_size * aspect_ratio)
    
    icon = icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Calculate position to center the icon
    icon_x = (qr_width - new_width) // 2
    icon_y = (qr_height - new_height) // 2
    
    # Create a copy of QR code to paste icon on
    qr_with_icon = qr_img.copy()
    
    # If icon has transparency, use it as mask
    if icon.mode == 'RGBA':
        qr_with_icon.paste(icon, (icon_x, icon_y), icon)
    else:
        qr_with_icon.paste(icon, (icon_x, icon_y))
    
    # Save the result
    qr_with_icon.save(output_path)
    print(f"QR code with icon saved to: {output_path}")
    
    return qr_with_icon

# Example usage
if __name__ == "__main__":
    # Your data to encode
    data = "https://esg.kylekaihin.org/booth/"
    
    # Path to your icon/logo image
    icon_path = "logo.png"  # Replace with your icon path
    
    # Output path
    output_path = "qr_with_icon.png"
    
    # Generate QR code with icon
    generate_qr_with_icon(data, icon_path, output_path)