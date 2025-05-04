from flask import Flask, request, render_template, redirect, url_for, session, send_file, after_this_request, flash
from fpdf import FPDF
import os
import re
import hashlib
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = os.urandom(24)
GENERATED_FOLDER = 'generated'
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# Store the username and hashed password
USER_CREDENTIALS = {
    'username': 'admin',
    'password': hashlib.sha256('Pass4%33word'.encode()).hexdigest()  # Hashed password
}

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp-mail.outlook.com'  # Replace with your SMTP server
app.config['MAIL_PORT'] = 587  # Replace with your SMTP server port
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'adamlucideld@outlook.com' # Your email here
app.config['MAIL_PASSWORD'] = 'Lucid2025Eld!'  # Your email password here
mail = Mail(app)

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USER_CREDENTIALS['username'] and hashlib.sha256(password.encode()).hexdigest() == USER_CREDENTIALS['password']:
            session['username'] = username
            print("Login successful, redirecting to dashboard")  # Debug log
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

@app.route('/generate_report', methods=['GET', 'POST'])
def generate_report():
    if request.method == 'POST':
        # Получаем данные из формы
        company = request.form['company']
        period = request.form['period']
        truck_number = request.form['truck_number']
        mileage_data_raw = request.form['mileage_data']
        logo_file = request.files.get('logo')

        # Словарь: полные названия штатов → сокращения
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

        # Приводим весь текст к нижнему регистру и очищаем от ненужных символов
        normalized_text = mileage_data_raw.lower()
        normalized_text = re.sub(r'[^\w\s().-]', ' ', normalized_text)

        # Заменяем полные названия штатов на аббревиатуры
        for full in sorted(state_map.keys(), key=len, reverse=True):
            abbr = state_map[full]
            normalized_text = re.sub(rf'\b{re.escape(full)}\b', abbr.lower(), normalized_text, flags=re.IGNORECASE)

        # Ищем все пары типа AL 88, (TX) 123.45, AL-88, и т.д.
        matches = re.findall(r'\(?\b([A-Z]{2})\b\)?[\s:\-]*([0-9]+(?:\.[0-9]+)?)', normalized_text.upper())

        # Складываем мили по штатам
        mileage_data = {}
        for state, miles_str in matches:
            try:
                miles = float(miles_str)
                mileage_data[state] = mileage_data.get(state, 0) + miles
            except ValueError:
                continue

        total_mileage = sum(mileage_data.values())

        # Класс для генерации PDF
        class StyledPDF(FPDF):
            def header(self):
                if logo_file and logo_file.filename != '':
                    logo_path = os.path.join(GENERATED_FOLDER, "temp_logo.png")
                    logo_file.save(logo_path)
                    self.image(logo_path, x=10, y=8, h=30)

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

        # Генерация PDF
        pdf = StyledPDF()
        pdf.add_page()
        pdf.add_table(truck_number, mileage_data, total_mileage)

        filename = f"{company.replace(' ', '_')}_{truck_number}_IFTA_Report.pdf"
        filepath = os.path.join(GENERATED_FOLDER, filename)
        pdf.output(filepath)

        # Очистка временного файла логотипа
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

@app.route('/eld-malfunction-letter', methods=['GET', 'POST'])
def eld_malfunction_letter():
    if request.method == 'GET':
        return render_template('eld_malfunction_letter.html')

    # Handle POST
    company = request.form['company_name']
    dot_number = request.form['dot_number']
    driver_name = request.form['driver_name']
    malfunction_date = request.form['malfunction_date']

    output_dir = 'generated_files'
    os.makedirs(output_dir, exist_ok=True)

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

    font_path = os.path.join('static', 'fonts', 'DejaVuSans.ttf')
    pdf = StyledPDF()
    pdf.add_font('DejaVu', '', font_path, uni=True)
    pdf.add_font('DejaVu', 'B', font_path, uni=True)
    pdf.add_font('DejaVu', 'I', font_path, uni=True)
    pdf.set_font('DejaVu', '', 12)
    pdf.add_page()

    # First page
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

    pdf.ln(10)
    pdf.set_font("DejaVu", "", 12)
    y_before = pdf.get_y()
    pdf.cell(90, 10, "LUCID ELD Manager, Sukhrobbek Usmonov", ln=0)
    sig_path = 'static/manager_signature.png'
    if os.path.exists(sig_path):
        try:
            pdf.image(sig_path, x=120, y=y_before, w=50)
        except Exception as e:
            print("Signature load error:", e)
    pdf.ln(25)
    pdf.cell(0, 10, f"Given date: {malfunction_date}", ln=True)

    # Second page
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
        bold_phrases=[
            "within 24 hours", "49 CFR 395.8", "paper logs",
            "Driver Printed Name", "Signature", "Date", "Time"
        ]
    )

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


@app.route("/tutorial")
def tutorial():
    return render_template("tutorial.html")

# Отправка email
@app.route('/mail', methods=['GET', 'POST'])
def mail():
    pdb.set_trace()
    # Получаем данные из формы
    email = request.form['email']
    email_type = request.form['email_type']
    message = ""
    
    # Шаблоны для каждого типа письма
    if email_type == "instructions":
        message = """
        Subject: Required ELD Instruction Pack – Please Print & Keep in Truck

        Hello,

        Attached you will find the official **ELD Instruction Pack** for Lucid ELD. These documents are **required by FMCSA** and **must be printed and kept in the truck at all times**.

        They provide essential guidance on how to operate the ELD system, handle malfunction procedures, and understand data transfer methods.

        If you have any questions or need help with anything, feel free to reach out—we’re here 24/7 to support you.

        Safe driving!

        Best regards,  
        Lucid ELD Support Team  
        www.lucideld.com
        """
    elif email_type == "ifta":
        message = """
        Subject: IFTA Report Attached

        Hello,

        As requested, please find attached the IFTA report(s) for your review.

        If you need assistance understanding or organizing these documents for your filings, don’t hesitate to reach out. We’re happy to help!

        Wishing you continued success and smooth operations.

        Best,  
        Lucid ELD Team  
        www.lucideld.com
        """
    elif email_type == "information":
        message = """
        Subject: About Lucid ELD – What We Offer

        Hello,

        Thank you for your interest in Lucid ELD! Here’s a quick overview of what we provide:

        - **FMCSA Certified ELD system**
        - **24/7 support from real humans**
        - **Dedicated individual assistance for every driver**
        - **IFTA calculation and reporting support**
        - **Live GPS tracking and trip history**
        - **User-friendly mobile app for iOS and Android**
        - **Instant malfunction & compliance alerts**
        - And much more...

        Our goal is to make your compliance journey as smooth, efficient, and stress-free as possible.

        If you’d like to get started or ask any questions, we’re always just a call or message away.

        Warm regards,  
        Lucid ELD Team  
        www.lucideld.com
        """
    elif email_type == "advertising":
        message = """
        Subject: A Better ELD Solution for Your Fleet

        Hello!

        Managing a fleet is challenging enough—your ELD system shouldn’t make it harder.

        At **Lucid ELD**, we’ve built a platform that just works:

        ✔ FMCSA-compliant, rock-solid performance  
        ✔ Real-time GPS tracking & automated IFTA reports  
        ✔ Transparent pricing—no hidden fees, ever  
        ✔ 24/7 live support from real humans (yes, real people!)  
        ✔ Easy-to-use app your drivers will actually like

        If your current system is frustrating—or if you just want something smoother and more reliable—we’d love to show you the difference.

        **Are you available for a quick 5-minute call today?**

        In the meantime, feel free to visit us at [www.lucideld.com](http://www.lucideld.com) or call me directly at (267) 578-8580.  
        Or just reply to this email—I’ll respond right away.

        Looking forward to helping you drive forward with confidence.

        Best,  
        Adam  
        Lucid ELD  
        📞 (267) 578-8580  
        🌐 www.lucideld.com
        """
    elif email_type == "api":
        username = request.form['username']
        password = request.form['password']
        api_key = request.form['api_key']

        message = f"""
        Hello,

        Here are the credentials and API Key you requested for accessing our system:

        **Username:** {username}  
        **Password:** {password}  
        **API Key:** {api_key}

        Please make sure to keep this information secure. You can use these credentials to access our API and integrate with our system.

        If you need further assistance or have any questions, don't hesitate to reach out.

        Best regards,  
        Lucid ELD Support Team
        """

    # Путь к файлам для прикрепления
    files = [
        "Users Manual.pdf",
        "Malfunction Manual.pdf",
        "Truck Sticker.pdf",
        "DOT Inspection.pdf",
        "Certificate of Compliance.pdf"
    ]
    
    full_files = []
    if email_type == "instructions":
        # Если тип письма - инструкции, прикрепляем файлы
        for file in files:
            file_path = os.path.join(INSTRUCTION_FOLDER, file)
            if os.path.exists(file_path):
                full_files.append(file_path)
            else:
                print(f"File {file} not found!")

    # Получаем файлы для IFTA
    if email_type == "ifta":
        ifta_files = request.files.getlist("ifta_files")
        for file in ifta_files:
            if file:
                # Сохраняем файлы в папку загрузки
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                full_files.append(file_path)
    
    # Отправка email
    try:
        # Создаем объект сообщения
        msg = MIMEMultipart()
        msg['From'] = "adamlucideld@outlook.com"
        msg['To'] = email
        msg['Subject'] = "Lucid ELD Instructions & Documents"

        # Добавляем текст в сообщение
        msg.attach(MIMEText(message, 'plain'))

        # Прикрепляем файлы
        for file in full_files:
            with open(file, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(file))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file)}"'
                msg.attach(part)

        # Отправляем письмо
        with smtplib.SMTP('smtp-mail.outlook.com', 587) as server:
            server.starttls()  # Шифрование
            server.login("adamlucideld@outlook.com", "Lucid2025Eld!")  # Логин и пароль
            server.sendmail("adamlucideld@outlook.com", email, msg.as_string())  # Отправка письма

        flash("Email successfully sent!", "success")
        return redirect('/')
    
    except Exception as e:
        flash(f"Failed to send email: {str(e)}", "error")
        return redirect('/')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
