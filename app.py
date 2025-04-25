from flask import Flask, request, send_file, render_template 
from fpdf import FPDF
import os

app = Flask(__name__)

@app.route('/')
def form():
    return render_template('index.html')

@app.route('/generate_report', methods=['POST'])
def generate_report():
    company = request.form['company']
    period = request.form['period']
    truck_number = request.form['truck_number']
    mileage_data_raw = request.form['mileage_data']
    logo_file = request.files.get('logo')

    # ✅ Автообъединение миль по штатам
    mileage_lines = mileage_data_raw.strip().split('\n')
    mileage_data = {}
    for line in mileage_lines:
        parts = line.strip().split()
        if len(parts) == 2:
            state, miles = parts
            try:
                miles = float(miles)
                if state in mileage_data:
                    mileage_data[state] += miles
                else:
                    mileage_data[state] = miles
            except ValueError:
                continue  # если не число, пропускаем

    # ✅ Автокалькуляция общего пробега
    total_mileage = sum(mileage_data.values())

    class MileagePDF(FPDF):
        def header(self):
            if logo_file and logo_file.filename != '':
                logo_path = "temp_logo.png"
                logo_file.save(logo_path)
                self.image(logo_path, x=10, y=10, w=30)
                self.ln(25)
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, company, ln=True, align="C")
            self.set_font("Arial", "", 12)
            self.cell(0, 10, f"{period}", ln=True, align="C")
            self.ln(10)

        def add_table(self, truck_number, data, total):
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, f"Truck {truck_number}", ln=True)
            self.set_fill_color(220, 220, 220)
            self.set_font("Arial", "B", 10)
            self.cell(60, 8, "State", 1, 0, "C", True)
            self.cell(60, 8, "Miles", 1, 1, "C", True)
            self.set_font("Arial", "", 10)
            for state, miles in data.items():
                self.cell(60, 8, state, 1)
                self.cell(60, 8, f"{miles:.2f}", 1, 1)
            self.set_font("Arial", "B", 11)
            self.cell(60, 8, "Total Mileage", 1)
            self.cell(60, 8, f"{total:.2f}", 1, 1)
            self.ln(10)

    pdf = MileagePDF()
    pdf.add_page()
    pdf.add_table(truck_number, mileage_data, total_mileage)

    filename = f"{company.replace(' ', '_')}_{truck_number}_IFTA_Report.pdf"
    pdf.output(filename)

    if logo_file and logo_file.filename != '' and os.path.exists("temp_logo.png"):
        os.remove("temp_logo.png")

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
