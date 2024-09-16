from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import qrcode
import io
import pdfkit
import logging
import csv
import chardet

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
import qrcode

def generate_certificates(template, csv_file):
    logging.debug(f"Attempting to read CSV file: {csv_file}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_file)
    
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
                
                logging.info(f"Successfully read file with encoding: {encoding}")
                file.seek(0)
                next(csv_reader)  # Skip header row
                
                problematic_rows = []
                valid_data = []
                
                for row_num, row in enumerate(csv_reader, start=2):
                    if len(row) != 3:
                        problematic_rows.append((row_num, row))
                    else:
                        valid_data.append(row)
                break
        
        except UnicodeDecodeError:
            logging.warning(f"Failed to decode with {encoding} encoding, trying next...")
            continue
    else:
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
        event_name = row['Event']
        cert_id = f"{student_name}_{index}"
        
        # Generate QR code for verification URL
        verification_url = f"http://yourwebsite.com/verify/{cert_id}"
        qr_code = qrcode.make(verification_url)
        
        # Resize QR code to be smaller
        qr_code = qr_code.resize((100, 100))  # Resize the QR code to be 100x100 pixels

        # Open the template and create a new certificate
        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)
        
        # Define font and placement for the recipient's name
        max_width = 700
        font_size = 60
        font_path = 'arial.ttf'
        font = ImageFont.truetype(font_path, font_size)
        text_bbox = draw.textbbox((0, 0), student_name, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        
        while text_width > max_width and font_size > 10:
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            text_bbox = draw.textbbox((0, 0), student_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]

        name_x = (image.width - text_width) // 2
        name_y = 400
        draw.text((name_x, name_y), student_name, font=font, fill='black')
        
        # Place QR code in the bottom-right corner
        qr_x = image.width - 150  # Position the QR code 150px from the right
        qr_y = image.height - 150  # Position the QR code 150px from the bottom
        image.paste(qr_code, (qr_x, qr_y))
        
        # Add a short verification URL under the QR code
        short_url = f"Verify at: {verification_url}"
        font_url = ImageFont.truetype('arial.ttf', 20)
        draw.text((qr_x, qr_y + 110), short_url, font=font_url, fill='black')
        
        # Save the certificate
        cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
        image.save(cert_path)

    return len(valid_data), len(problematic_rows)

@app.route('/verify/<cert_id>')
def verify(cert_id):
    cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
    if os.path.exists(cert_path):
        return f"Certificate {cert_id} is verified and valid."
    else:
        return "This certificate is invalid or does not exist."

# Route to handle the verification form submission
@app.route('/verify_certificate', methods=['GET'])
def verify_certificate():
    cert_id = request.args.get('cert_id')  # Get the certificate ID from the form input
    return redirect(url_for('verify', cert_id=cert_id))  # Redirect to the verification route

# HTML template rendering (could be 'verify.html')
@app.route('/certificate_form')
def certificate_form():
    return render_template('verify.html')  # The form for manually entering cert_id

# Route for participants to download certificates
@app.route('/download/<cert_id>')
def download(cert_id):
    cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
    return send_file(cert_path, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)