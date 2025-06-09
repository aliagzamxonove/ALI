from flask import Flask, request, render_template, redirect, current_app, url_for, session, send_file, after_this_request, flash
from fpdf import FPDF
import logging
import os
import re
import hashlib
import html
import mimetypes
import markdown
from flask_mail import Mail, Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from markdown import markdown
import smtplib
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- Setup Logger --------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------- Flask App Setup --------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)

# -------------------- Folders --------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
GENERATED_FOLDER = os.path.join(BASE_DIR, 'generated')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
INSTRUCTION_FOLDER = os.path.join(BASE_DIR, 'Instruction')
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(INSTRUCTION_FOLDER, exist_ok=True)

# -------------------- Credentials --------------------
USER_CREDENTIALS = {
    'username': 'admin',
    'password': generate_password_hash('Pass4%33word')
}

# -------------------- Mail Configuration --------------------
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", 'bluestarelduzb@gmail.com'),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", 'xmuz oyrx zdda qywm'),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", 'bluestarelduzb@gmail.com')
)

mail = Mail(app)

# -------------------- Helper --------------------
def strip_html_tags(text):
    return re.sub(r'<[^>]+>', '', text)

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username == USER_CREDENTIALS['username'] and check_password_hash(USER_CREDENTIALS['password'], password):
            session['username'] = username
            logger.info(f"User {username} logged in successfully.")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'error')
            logger.warning(f"Failed login attempt for username: {username}")
            return redirect(url_for('login'))

    return render_template('login.html')

# Dashboard page
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', username=session['username'])

@app.route('/generate_report', methods=['GET', 'POST'])
def generate_report():
    if request.method == 'POST':
        company = html.escape(request.form['company'])
        period = html.escape(request.form['period'])
        truck_number = html.escape(request.form['truck_number'])
        mileage_data_raw = request.form['mileage_data']
        logo_file = request.files.get('logo')

        # Full state names → abbreviations
        state_map = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
            'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
            'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA',
            'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT',
            'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM',
            'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
            'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
            'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
        }

        # Normalize and parse mileage data
        normalized_text = mileage_data_raw.lower()
        normalized_text = re.sub(r'[^\w\s().-]', ' ', normalized_text)

        for full in sorted(state_map.keys(), key=len, reverse=True):
            abbr = state_map[full]
            normalized_text = re.sub(rf'\b{re.escape(full)}\b', abbr.lower(), normalized_text, flags=re.IGNORECASE)

        matches = re.findall(r'\(?\b([A-Z]{2})\b\)?[\s:\-]*([0-9]+(?:\.[0-9]+)?)', normalized_text.upper())

        mileage_data = {}
        for state, miles_str in matches:
            try:
                miles = float(miles_str)
                mileage_data[state] = mileage_data.get(state, 0) + miles
            except ValueError:
                continue

        total_mileage = sum(mileage_data.values())

        # Save logo temporarily
        logo_temp_path = None
        if logo_file and logo_file.filename != '':
            logo_temp_path = os.path.join(GENERATED_FOLDER, "temp_logo.png")
            logo_file.save(logo_temp_path)

        class StyledPDF(FPDF):
            def header(self):
                if logo_temp_path and os.path.exists(logo_temp_path):
                    self.image(logo_temp_path, x=10, y=8, h=30)

                self.set_font("Helvetica", "B", 18)
                self.set_text_color(0, 51, 102)
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

                self.set_fill_color(230, 230, 230)
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

        safe_company = re.sub(r'[^a-zA-Z0-9_\-]', '_', company)
        filename = f"{safe_company}_{truck_number}_IFTA_Report.pdf"
        filepath = os.path.join(GENERATED_FOLDER, filename)
        pdf.output(filepath)

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                if logo_temp_path and os.path.exists(logo_temp_path):
                    os.remove(logo_temp_path)
            except Exception as e:
                print(f"Cleanup error: {e}")
            return response

        return send_file(filepath, mimetype='application/pdf', as_attachment=True, download_name=filename)

    return render_template('generate_report.html')
    
    
@app.route('/eld_malfunction_letter', methods=['GET', 'POST'])
def eld_malfunction_letter():
    if 'username' not in session:
        flash('Please log in to access the page.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('eld_malfunction_letter.html', username=session['username'])

    # Extract form data
    company = request.form.get('company_name', 'N/A')
    dot_number = request.form.get('dot_number', 'N/A')
    driver_name = request.form.get('driver_name', 'N/A')
    malfunction_date = request.form.get('malfunction_date', 'N/A')

    output_dir = 'generated_files'
    os.makedirs(output_dir, exist_ok=True)

    # Define PDF class
    class StyledPDF(FPDF):
        def header(self):
            if self.page_no() == 1:
                logo_path = os.path.join('static', 'logo.png')
                if os.path.exists(logo_path):
                    self.image(logo_path, x=60, y=10, w=90)
                self.ln(40)
            self.set_font("DejaVu", "B", 16)
            self.cell(0, 10, "ELD MALFUNCTION CONFIRMATION", 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("DejaVu", "I", 8)
            self.cell(0, 10, f"Page {self.page_no()}", 0, 0, 'C')

        def chapter_body(self, body, bold_phrases=None):
            self.set_font("DejaVu", "", 12)
            if not bold_phrases:
                self.multi_cell(0, 10, body)
                return
            parts = [body]
            for phrase in bold_phrases:
                temp = []
                for part in parts:
                    if phrase in part:
                        before, after = part.split(phrase, 1)
                        temp.extend([before, phrase, after])
                    else:
                        temp.append(part)
                parts = temp
            for part in parts:
                if part in bold_phrases:
                    self.set_font("DejaVu", "B", 12)
                    self.write(10, part)
                    self.set_font("DejaVu", "", 12)
                else:
                    self.write(10, part)
            self.ln(10)

    # Font paths
    fonts_dir = os.path.join('static', 'fonts')
    regular_font_path = os.path.join(fonts_dir, 'DejaVuSans.ttf')
    bold_font_path = os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')
    italic_font_path = os.path.join(fonts_dir, 'DejaVuSans-Oblique.ttf')

    # Validate font files
    if not all(os.path.exists(f) for f in [regular_font_path, bold_font_path, italic_font_path]):
        return "Required font files missing (DejaVuSans.ttf, DejaVuSans-Bold.ttf, DejaVuSans-Oblique.ttf).", 500

    # Initialize PDF
    pdf = StyledPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Register fonts
    pdf.add_font('DejaVu', '', regular_font_path, uni=True)
    pdf.add_font('DejaVu', 'B', bold_font_path, uni=True)
    pdf.add_font('DejaVu', 'I', italic_font_path, uni=True)

    pdf.set_font("DejaVu", "", 12)
    pdf.add_page()

    # Page 1 content
    pdf.chapter_body(
        f"""To whom it may concern,

This letter confirms that the ELD system is currently in malfunction. We are aware of the issue and are working to resolve it.

Company USDOT: {dot_number}
Company Name: {company}
Driver Name: {driver_name}

In accordance with 49 CFR 395.8, until the ELD is serviced and back in compliance, the driver has been allowed to use paper logs for no more than 8 days. The recording of the driver’s hours of service on a paper log begins on {malfunction_date}.
""",
        bold_phrases=["49 CFR 395.8", "paper logs for no more than 8 days."]
    )

    # Signature block
    y_before = pdf.get_y()
    pdf.cell(90, 10, "LUCID ELD Manager, Sukhrobbek Usmonov", ln=0)

    sig_path = os.path.join('static', 'manager_signature.png')
    if os.path.exists(sig_path):
        try:
            pdf.image(sig_path, x=120, y=y_before, w=50)
        except Exception as e:
            print("Signature load error:", e)

    pdf.ln(25)
    pdf.cell(0, 10, f"Given date: {malfunction_date}", ln=True)

    # Page 2 content
    pdf.add_page()
    pdf.chapter_body("If an ELD malfunctions, a driver must:")
    pdf.chapter_body(
        """- Note the malfunction of the ELD and provide written notice of the malfunction to the motor carrier within 24 hours;
- Reconstruct the record of duty status (RODS) for the current 24-hour period and the previous 7 consecutive days, and record the records of duty status on graph-grid paper logs that comply with 49 CFR 395.8, unless the driver already has the records or retrieves them from the ELD;
- Continue to manually prepare RODS in accordance with 49 CFR 395.8 until the ELD is serviced and back in compliance.

In compliance with the above-mentioned USDOT rules and regulations, I ______ certify that all information provided by me is true and correct to the best of my knowledge, and that I notified the company Safety Department of an ELD malfunction within 24-hours.

The reason of malfunction was:
☐ Device (Tablet) is powered off and cannot be recharged and is not working properly;
☐ ELD device does not show any lights when connected to diagnostic port or shows power off;
☐ ELD Device not reporting any information with Device (Tablet) when connected to the Truck;

Driver Printed Name: ________     Signature: ________     Date: ________     Time: ________
""",
        bold_phrases=["within 24 hours", "49 CFR 395.8", "paper logs", "Driver Printed Name", "Signature", "Date", "Time"]
    )

    # Save PDF
    output_path = os.path.join(output_dir, 'eld_malfunction_letter.pdf')
    pdf.output(output_path)

    @after_this_request
    def cleanup(response):
        try:
            os.remove(output_path)
        except Exception as e:
            print(f"Cleanup error: {e}")
        return response

    return send_file(output_path, mimetype='application/pdf', as_attachment=True,
                     download_name='ELD_Malfunction_Letter.pdf')


@app.route('/timezones')
def timezones():
    return render_template('timezones.html')


@app.route('/tutorial')
def tutorial():
    return render_template('tutorial.html')


# -------------------- Mail Page --------------------
@app.route('/mail', methods=['GET', 'POST'])
def mail_page():
    if 'username' not in session:
        flash('Please log in to access the page.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        email = request.form.get('email')
        email_type = request.form.get('email_type')

        if not email or not email_type:
            flash("Email and email type are required!", "error")
            return redirect(url_for('mail_page'))

        subject = html_message = None
        attachments = []

        try:
            if email_type == "instructions":
                subject = "Required ELD Instruction Pack – Please Print & Keep in Truck"
                html_message = render_template('emails/instructions.html')
                for fname in [
                    "Users Manual.pdf", "Malfunction Manual.pdf", "Truck Sticker.pdf",
                    "DOT Inspection.pdf", "Certificate of Compliance.pdf"
                ]:
                    path = os.path.join(INSTRUCTION_FOLDER, fname)
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            part = MIMEApplication(f.read(), Name=fname)
                            attachments.append((fname, part))
                    else:
                        flash(f"File not found: {fname}", "error")

            elif email_type == "ifta":
                subject = "IFTA Report Attached"
                html_message = render_template('emails/ifta.html')
                uploaded = request.files.getlist("ifta_files")
                if not uploaded:
                    flash("No IFTA file supplied", "error")
                    return redirect(url_for('mail_page'))
                for f in uploaded:
                    if f and f.filename:
                        part = MIMEApplication(f.read(), Name=f.filename)
                        attachments.append((f.filename, part))

            elif email_type == "information":
                subject = "About Lucid ELD – What We Offer"
                html_message = render_template('emails/information.html')

            elif email_type == "advertising":
                subject = "A Better ELD Solution for Your Fleet"
                html_message = render_template('emails/advertising.html')

            elif email_type == "api":
                username = request.form.get('username')
                password_field = request.form.get('password')
                api_key = request.form.get('api_key')
                if not all([username, password_field, api_key]):
                    flash("Username, Password, and API Key are required!", "error")
                    return redirect(url_for('mail_page'))
                subject = "API Credentials and Key"
                html_message = render_template(
                    'emails/api.html',
                    username=username,
                    password=password_field,
                    api_key=api_key
                )

            else:
                flash("Unknown email type!", "error")
                return redirect(url_for('mail_page'))

            msg = Message(subject=subject, recipients=[email])
            msg.body = strip_html_tags(html_message)
            msg.html = html_message

          # Inline logo attachment (optional)
logo_path = os.path.join(BASE_DIR, 'static/logolucid.gif')
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img:
        msg.attach(
            filename="logolucid.gif",
            content_type="image/gif",
            data=img.read(),
            disposition='inline',
            headers={"Content-ID": "<logolucid>"}   # dict, not list
        )
else:
    logger.warning("Logo not found. Skipping inline logo.")

            # Attach additional files
            for fname, part in attachments:
                msg.attach(
                    filename=fname,
                    content_type='application/octet-stream',
                    data=part.get_payload(decode=True)
                )

            mail.send(msg)
            flash("Email successfully sent!", "success")

        except Exception as e:
            logger.error(f"Email sending failed: {e}", exc_info=True)
            flash(f"Failed to send email: {str(e)}", "error")

        return redirect(url_for('mail_page'))

    return render_template('mail.html')
    
@app.route('/eldquiz')
def eldquiz():
    return render_template('eldquiz.html')

@app.route('/supportresources')
def supportresources():
    return render_template('supportresources.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
