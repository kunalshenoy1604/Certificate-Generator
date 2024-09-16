from flask import Flask, render_template, request, send_file, url_for
import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import qrcode
import logging
import csv

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Path configuration
UPLOAD_FOLDER = 'uploads/'
CERTIFICATE_FOLDER = 'certificates/'
VERIFICATION_FOLDER = 'verification/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CERTIFICATE_FOLDER'] = CERTIFICATE_FOLDER

# Admin route: Upload template and data
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        try:
            template = request.files['template']
            csv_file = request.files['csv_data']
            template.save(os.path.join(app.config['UPLOAD_FOLDER'], template.filename))
            csv_file.save(os.path.join(app.config['UPLOAD_FOLDER'], csv_file.filename))
            processed_rows, skipped_rows = generate_certificates(template.filename, csv_file.filename)
            
            result_message = f"Certificates generated successfully for {processed_rows} entries."
            if skipped_rows > 0:
                result_message += f" {skipped_rows} rows were skipped due to formatting issues. Check the server logs for details."
            
            return result_message
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            return f"An unexpected error occurred: {str(e)}"
    return render_template('admin.html')

# Function to generate certificates
def generate_certificates(template, csv_file):
    logging.debug(f"Attempting to read CSV file: {csv_file}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_file)
    
    # List of encodings to try
    encodings = ['utf-8', 'iso-8859-1', 'windows-1252', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                csv_reader = csv.reader(file)
                headers = next(csv_reader, None)  # Read the header row
                
                if not headers:
                    continue  # Try next encoding if file is empty
                
                if len(headers) != 3:
                    raise ValueError(f"Expected 3 columns (Name, Event, Date), but found {len(headers)}: {', '.join(headers)}")
                
                # Reset file pointer to beginning
                file.seek(0)
                next(csv_reader)  # Skip header row
                
                problematic_rows = []
                valid_data = []
                
                for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 as row 1 is headers
                    if len(row) != 3:
                        problematic_rows.append((row_num, row))
                    else:
                        valid_data.append(row)
                
                break  # Successfully read the file, exit the loop
        
        except UnicodeDecodeError:
            logging.warning(f"Failed to decode with {encoding} encoding, trying next...")
            continue
    else:
        # If we've exhausted all encodings
        raise ValueError("Unable to read the CSV file. The file might be corrupted or use an unsupported encoding.")

    if problematic_rows:
        logging.warning(f"Found {len(problematic_rows)} problematic rows in the CSV file:")
        for row_num, row in problematic_rows:
            logging.warning(f"Row {row_num}: {row}")
    
    # Convert valid data to DataFrame
    data = pd.DataFrame(valid_data, columns=['Name', 'Event', 'Date'])
    
    template_path = os.path.join(app.config['UPLOAD_FOLDER'], template)

    for index, row in data.iterrows():
        student_name = row['Name']
        cert_id = f"{student_name}_{index}"

        # Generate the validation URL
        validation_url = url_for('verify', cert_id=cert_id, _external=True)

        # Open the template and create a new certificate
        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)
        
        # Define font and placement for the recipient's name
        max_width = 700  # Maximum allowed width for the name on the certificate
        font_size = 60  # Initial font size
        font_path = 'arial.ttf'  # Path to the font

        # Adjust font size dynamically based on name length
        font = ImageFont.truetype(font_path, font_size)
        text_bbox = draw.textbbox((0, 0), student_name, font=font)
        text_width = text_bbox[2] - text_bbox[0]  # width of the text

        while text_width > max_width and font_size > 10:  # Ensure font size does not go below 10
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            text_bbox = draw.textbbox((0, 0), student_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]

        # Center the text horizontally
        name_x = (image.width - text_width) // 2
        name_y = 400  # Adjust vertical position as necessary
        
        draw.text((name_x, name_y), student_name, font=font, fill='black')
        
        # Generate the QR code pointing to the validation URL
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(validation_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill='black', back_color='white')

        # Position the QR code on the certificate (right-hand corner)
        qr_position = (image.width - 200, image.height - 200)  # Adjust position as needed
        qr_img = qr_img.resize((150, 150))  # Resize the QR code if necessary
        image.paste(qr_img, qr_position)

        # Save the certificate as a PDF
        cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
        image.save(cert_path)

    return len(valid_data), len(problematic_rows)

# Route for participants to download certificates
@app.route('/download/<cert_id>')
def download(cert_id):
    cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
    return send_file(cert_path, as_attachment=True)

# Verification route
@app.route('/verify/<cert_id>')
def verify(cert_id):
    cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
    if os.path.exists(cert_path):
        return render_template('verification.html', cert_id=cert_id)
    else:
        return "Certificate not found or invalid."

if __name__ == '__main__':
    app.run(debug=True)
