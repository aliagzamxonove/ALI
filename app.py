from flask import Flask, request, render_template, redirect, url_for, session, send_file, after_this_request, flash
from fpdf import FPDF
import os
import hashlib

app = Flask(__name__)
app.secret_key = os.urandom(24)  # for sessions
GENERATED_FOLDER = 'generated'
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# Mock user credentials with hashed password
USER_CREDENTIALS = {'username': 'admin', 'password': hashlib.sha256('password'.encode()).hexdigest()}

# Main page, redirects to login
@app.route('/')
def home():
    return redirect(url_for('login'))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USER_CREDENTIALS['username'] and hashlib.sha256(password.encode()).hexdigest() == USER_CREDENTIALS['password']:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'error')
            return redirect(url_for('login'))  # Ensure to redirect after flashing the message
    return render_template('login.html')

# Dashboard page
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    return render_template('dashboard.html', username=username)

# Report generation page
@app.route('/generate_report', methods=['GET', 'POST'])
def generate_report():
    if request.method == 'POST':
        # Get form data
        company = request.form['company']
        period = request.form['period']
        truck_number = request.form['truck_number']
        mileage_data_raw = request.form['mileage_data']
        logo_file = request.files.get('logo')

        # Parse mileage data
        mileage_data = {}
        for line in mileage_data_raw.strip().split('\n'):
            cleaned_line = line.strip().replace('\t', ' ')
            parts = [p for p in cleaned_line.split(' ') if p]
            if len(parts) >= 2:
                state = parts[0]
                miles_str = parts[1].lower().replace('mi', '').replace(',', '').strip()
                try:
                    miles = float(miles_str)
                    mileage_data[state] = mileage_data.get(state, 0) + miles
                except ValueError:
                    continue

        total_mileage = sum(mileage_data.values())

        class StyledPDF(FPDF):
            def header(self):
                if logo_file and logo_file.filename != '':
                    logo_path = os.path.join(GENERATED_FOLDER, "temp_logo.png")
                    logo_file.save(logo_path)
                    self.image(logo_path, x=10, y=8, h=30)

                self.set_font("Helvetica", "B", 18)
                self.set_text_color(0, 51, 102)  # Official color theme
                self.ln(10)
                self.cell(0, 10, "IFTA REPORT", ln=True, align="C")
                self.ln(5)
                self.set_font("Helvetica", "B", 16)
                self.set_text_color(0, 0, 0)
                self.cell(0, 10, company, ln=True, align="C")
                self.set_font("Helvetica", "", 12)
                self.cell(0, 10, f"Period: {period}", ln=True, align="C")
                self.ln(10)

            def add_table(self, truck_number, data, total):
                self.set_font("Helvetica", "B", 12)
                self.cell(0, 10, f"Truck Number: {truck_number}", ln=True, align="L")
                self.ln(4)

                self.set_fill_color(230, 230, 230)  # Subtle background shading for readability
                self.set_text_color(0)
                self.set_draw_color(180, 180, 180)
                col_width = 90
                self.set_font("Helvetica", "B", 10)
                self.cell(col_width, 8, "State", border=1, align="C", fill=True)
                self.cell(col_width, 8, "Miles", border=1, align="C", fill=True)
                self.ln()
                self.set_font("Helvetica", "", 10)

                for state, miles in data.items():
                    self.cell(col_width, 8, state, border=1)
                    self.cell(col_width, 8, f"{miles:.2f}", border=1, align="R")
                    self.ln()

                self.set_font("Helvetica", "B", 10)
                self.cell(col_width, 8, "Total Mileage", border=1)
                self.cell(col_width, 8, f"{total:.2f}", border=1, align="R")
                self.ln(10)

        pdf = StyledPDF()
        pdf.add_page()
        pdf.add_table(truck_number, mileage_data, total_mileage)

        filename = f"{company.replace(' ', '_')}_{truck_number}_IFTA_Report.pdf"
        filepath = os.path.join(GENERATED_FOLDER, filename)
        pdf.output(filepath)

        # Cleanup logo file after report generation
        if logo_file and logo_file.filename != '':
            logo_temp_path = os.path.join(GENERATED_FOLDER, "temp_logo.png")
            if os.path.exists(logo_temp_path):
                os.remove(logo_temp_path)

        @after_this_request
        def remove_file(response):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting PDF: {e}")
            return response

        return send_file(filepath, mimetype='application/pdf', as_attachment=True, download_name=filename)

    return render_template('generate_report.html')

# Time zone page
@app.route('/timezones')
def timezones():
    return render_template('timezones.html')

# Logout page
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
