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
                
                # If we've made it this far, we've successfully read the file
                logging.info(f"Successfully read file with encoding: {encoding}")
                
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
        event_name = row['Event']
        date = row['Date']

        # Open the template and create a new certificate
        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)
        
        # Define font and placement (hardcoded, can be dynamic via Canvas.js)
        font = ImageFont.truetype('arial.ttf', 40)
        draw.text((500, 300), student_name, font=font, fill='black')
        draw.text((500, 400), event_name, font=font, fill='black')
        draw.text((500, 500), date, font=font, fill='black')

        # Generate QR code for verification
        cert_id = f"{student_name}_{index}"
        qr = qrcode.make(f"http://localhost:5000/verify/{cert_id}")
        image.paste(qr, (50, 50))

        # Save the certificate
        cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
        image.save(cert_path)
        
        # Store verification data
        with open(f'{VERIFICATION_FOLDER}{cert_id}.txt', 'w') as f:
            f.write(f"Name: {student_name}\nEvent: {event_name}\nDate: {date}\nVerified at: {cert_id}")

    return len(valid_data), len(problematic_rows)

# Route for participants to download certificates
@app.route('/download/<cert_id>')
def download(cert_id):
    cert_path = os.path.join(app.config['CERTIFICATE_FOLDER'], f"{cert_id}.pdf")
    return send_file(cert_path, as_attachment=True)

# Verification route
@app.route('/verify/<cert_id>')
def verify(cert_id):
    try:
        with open(f'{VERIFICATION_FOLDER}{cert_id}.txt', 'r') as f:
            details = f.read()
        return f"Certificate Verified:<br>{details}"
    except FileNotFoundError:
        return "Certificate not found or invalid."

if __name__ == '__main__':
    app.run(debug=True)