import os
from datetime import datetime
from fpdf import FPDF

class TokenProcessor:
    def __init__(self):
        try: 
            from database_manager import RayaDB
            self.db = RayaDB()
        except: self.db = None
        self.logo_path = "image_1.jpeg" 

    def get_triage_info(self, report):
        rep = str(report).lower()
        dept, color, level = "GENERAL MEDICINE", (0, 128, 0), "NORMAL (GREEN)"
        
        # 1. Immediate Life-Threatening Emergency Override
        if any(x in rep for x in ["heart attack", "stroke", "unconscious", "passed out", "severe chest pain", "can't breathe", "gasping"]): 
            return "EMERGENCY DEPT", (255, 0, 0), "EMERGENCY (RED)"
            
        # 2. Specific Departments
        if any(x in rep for x in ["heart", "chest pain", "cardiac", "shortness of breath", "palpitation", "heavy chest", "angina"]): 
            dept, color, level = "CARDIOLOGY", (255, 0, 0), "EMERGENCY (RED)"
        elif any(x in rep for x in ["headache", "migraine", "brain", "seizure", "dizzy", "vertigo", "faint", "numbness", "tingling", "paralysis", "concussion", "head injury", "tremor"]): 
            dept, color, level = "NEUROLOGY", (255, 165, 0), "URGENT (YELLOW)"
        elif any(x in rep for x in ["fracture", "bone", "joint", "sprain", "ligament", "ortho", "broken", "twisted ankle", "knee pain", "spine", "shoulder pain", "arthritis", "muscle tear"]): 
            dept, color, level = "ORTHOPEDICS", (255, 165, 0), "URGENT (YELLOW)"
        elif any(x in rep for x in ["stomach", "abdomen", "gastric", "vomit", "puke", "diarrhea", "liver", "constipation", "nausea", "heartburn", "acid reflux", "ulcer", "food poisoning", "loose motion"]): 
            dept, color, level = "GASTROENTEROLOGY", (0, 128, 0), "NORMAL (GREEN)"
        elif any(x in rep for x in ["tooth", "dental", "gum", "dentist", "cavity", "toothache", "root canal", "jaw pain"]): 
            dept, color, level = "DENTAL DEPT", (0, 128, 0), "NORMAL (GREEN)"
        elif any(x in rep for x in ["eye", "vision", "blur", "blind", "cataract", "conjunctivitis", "squint"]): 
            dept, color, level = "OPHTHALMOLOGY", (0, 128, 0), "NORMAL (GREEN)"
        elif any(x in rep for x in ["ear", "nose", "throat", "hearing", "deaf", "sinus", "tonsil", "sore throat", "nosebleed", "swallow"]): 
            dept, color, level = "ENT DEPT", (0, 128, 0), "NORMAL (GREEN)"
        elif any(x in rep for x in ["skin", "rash", "itch", "acne", "pimple", "allergy", "hives", "eczema", "burn", "hair loss", "blister", "dermatitis"]): 
            dept, color, level = "DERMATOLOGY", (0, 128, 0), "NORMAL (GREEN)"
        elif any(x in rep for x in ["pregnancy", "pregnant", "period", "menstruation", "vaginal", "uterus", "cramp", "gynecology", "maternity", "miscarriage"]): 
            dept, color, level = "GYNECOLOGY", (255, 165, 0), "URGENT (YELLOW)"
            
        return dept, color, level

    def generate_pdf(self, data, report, dept_name, triage_color, triage_level):
        try:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens")
            if not os.path.exists(base_dir):
                os.makedirs(base_dir, exist_ok=True)
            
            path = os.path.join(base_dir, f"{data['sub_token']}.pdf")

            pdf = FPDF()
            pdf.add_page()
            
            # 1. Header
            pdf.set_font("Arial", 'B', 22); pdf.set_text_color(0, 51, 102) 
            pdf.cell(0, 12, "OXWAY SMART HEALTHCARE", align='L', ln=1); pdf.ln(5)
            
            if data.get('photo_path') and os.path.exists(data['photo_path']):
                pdf.image(data['photo_path'], x=160, y=10, w=35)

            # 2. Token IDs
            pdf.set_font("Arial", 'B', 14); pdf.set_text_color(0)
            pdf.cell(70, 12, f"MAJOR ID: {data['major_id']}", border=1, align='C')
            pdf.cell(70, 12, f"SUB TOKEN: {data['sub_token']}", border=1, align='C')
            pdf.ln(18)
            
            # 3. Triage Color Bar
            pdf.set_fill_color(*triage_color); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 12)
            pdf.cell(140, 10, f" DEPT: {dept_name} | PRIORITY: {triage_level}", fill=True, align='C'); pdf.ln(15)

            # 4. Patient Details
            pdf.set_text_color(0); pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, f"PATIENT: {str(data['name']).upper()}"); pdf.ln(6)
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 8, f"AGE: {data['age']} | MOBILE: {data['mobile']} | DATE: {data['date']}")
            pdf.ln(10); pdf.line(10, pdf.get_y(), 150, pdf.get_y()); pdf.ln(5)

            # 5. CLINICAL SUMMARY
            pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "CLINICAL SUMMARY & FINDINGS:"); pdf.ln(8)
            pdf.set_font("Arial", '', 10)
            
            points = str(report).split('\n')
            for point in points:
                point = point.replace('–', '-').replace('—', '-').replace('”', '"').replace('“', '"')
                clean_text = "".join(i for i in point if ord(i) < 128).replace('*', '').replace('#', '').strip()
                
                # Strip out any AI-generated numbered lists or bullet sequences
                while len(clean_text) > 0 and clean_text[0] in '0123456789-. \t':
                    clean_text = clean_text[1:]
                
                clean_text = clean_text.strip()
                if len(clean_text) > 3:
                    pdf.set_x(15); pdf.multi_cell(160, 7, f"- {clean_text}"); pdf.ln(1)

            # 6. Footer
            pdf.set_y(-20); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 10, "Generated by RAYA AI - Oxway Smart Healthcare Systems", align='C')

            pdf.output(path); return path
        except Exception as e:
            print(f"PDF Error: {e}"); return None

    def process_user_dynamic(self, patient_data, report, original_problem="General Checkup"):
        dept, color, level = self.get_triage_info(report)
        today = datetime.now().strftime("%Y-%m-%d")
        major_count, dept_count = 0, 0
        if self.db: major_count, dept_count = self.db.get_counts(today, dept)

        data = {
            "name": patient_data['name'], "age": patient_data['age'], 
            "mobile": patient_data['mobile'], "date": today,
            "major_id": major_count + 1, 
            "sub_token": f"{dept[:4].upper()}-{(dept_count + 1):03d}",
            "main_problem": original_problem,
            "photo_path": patient_data.get('photo_path')
        }
        if self.db: self.db.save_token(today, data['sub_token'], dept, data['name'])
        return data, self.generate_pdf(data, report, dept, color, level)