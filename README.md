# 🤖 Google Form Automation Bot

บอทอัตโนมัติสำหรับกรอกและส่งคำตอบ Google Forms พัฒนาด้วยภาษา **Python 3.10+**  
รองรับทั้งโหมด **Direct HTTP POST (ความเร็วสูงหลักเสี้ยววินาที)** และโหมด **Browser Automation (ผ่าน Playwright จำลองการเปิดเบราว์เซอร์จริง)**

---

## 🌟 จุดเด่นและความสามารถ (Features)

1. **Auto-Parser ดึงคำถามอัตโนมัติ**:
   - เพียงแค่วางลิงก์ Google Form บอทจะวิเคราะห์ชื่อคำถาม, ชนิดของฟิลด์ (Short text, Paragraph, Multiple choice, Checkbox, Dropdown, Linear scale, Date, Time) และรหัสตัวแปร `entry.xxxxxxxx` ให้ทันที
   - สร้างไฟล์ต้นแบบ `data/responses_template.csv` และไฟล์คอนฟิก `config/form_config.yaml` ให้อัตโนมัติ ไม่ต้องแกะโค้ดเอง

2. **2 โหมดการส่งข้อมูล**:
   - ⚡ **Direct HTTP POST Mode**: ยิงส่งข้อมูลตรงไปยัง Google Forms endpoint ทำงานเร็วมาก (เหมาะกับการทดสอบหรือส่งข้อมูลจำนวนมากโดยไม่ต้องเปิดหน้าต่างเบราว์เซอร์)
   - 🌐 **Browser Automation Mode (Playwright)**: เปิดเบราว์เซอร์ Chromium จริง กรอกข้อมูลทีละช่อง เหมาะกับฟอร์มที่มีหลายขั้นตอน (Multi-page form), ฟอร์มที่ต้องตรวจสอบด้วยสายตา หรือเปิดดูการทำงานแบบสดๆ ได้ (`--headed`)

3. **รองรับแหล่งข้อมูลหลากหลาย**:
   - อ่านข้อมูลจากไฟล์ `.csv`, `.xlsx` (Excel) หรือ `.json`
   - สามารถใช้หัวตารางเป็น "ชื่อคำถามภาษาไทย" ได้โดยตรง ตัวบอทมีระบบจับคู่ (Mapping) ให้โดยอัตโนมัติ
   - มีระบบ **สุ่มคำตอบอัตโนมัติ (Randomizer)** ตามตัวเลือกที่มีในแบบฟอร์ม สำหรับใช้ทดสอบระบบ

4. **ระบบบันทึก Log และภาพถ่ายหน้าจอ**:
   - บันทึกประวัติการส่งสำเร็จ/ล้มเหลวลงใน `logs/submission.log`
   - ในโหมดเบราว์เซอร์ สามารถบันทึกภาพหน้าจอ Screenshot เมื่อส่งคำตอบเสร็จหรือเมื่อเกิดข้อผิดพลาด

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
d:\Project\BOT\
├── config\
│   └── form_config.yaml         # ไฟล์คอนฟิก URL ฟอร์ม, ฟิลด์คำถาม และความหน่วงเวลา
├── data\
│   ├── responses.csv            # ไฟล์ข้อมูลคำตอบจริง (CSV/Excel)
│   └── responses_template.csv   # ไฟล์ต้นแบบที่ระบบสร้างให้หลัง Parse ฟอร์ม
├── logs\
│   ├── submission.log           # บันทึกประวัติการส่ง
│   └── screenshots\             # ภาพถ่ายหน้าจอผลลัพธ์ (โหมด Browser)
├── src\
│   ├── __init__.py
│   ├── parser.py                # ระบบสกัดข้อมูลจาก Google Form
│   ├── data_loader.py           # ตัวอ่านไฟล์ CSV/Excel/JSON และระบบสุ่มคำตอบ
│   ├── direct_submitter.py      # ตัวส่งข้อมูลผ่าน HTTP POST Request
│   ├── browser_submitter.py     # ตัวส่งข้อมูลผ่าน Playwright Chromium
│   └── main.py                  # สคริปต์หลัก (CLI & Interactive Menu)
├── tests\
│   └── test_bot.py              # ระบบทดสอบ Unit Tests
├── requirements.txt             # รายการ Libraries ที่ใช้งาน
└── README.md                    # คู่มือการใช้งาน
```

---

## 🛠 การติดตั้ง (Installation)

1. ติดตั้งไลบรารีที่จำเป็น:
```powershell
pip install -r requirements.txt
```

2. ติดตั้ง Chromium Browser สำหรับ Playwright:
```powershell
python -m playwright install chromium
```

---

## 🚀 วิธีการใช้งาน (How to Use)

### 1. ใช้งานผ่านเมนูคำสั่ง Interactive (ง่ายที่สุด)
เพียงพิมพ์คำสั่ง:
```powershell
python src/main.py
```
จะมีเมนูภาษาไทยให้เลือกทำรายการตามขั้นตอน เช่น วิเคราะห์ฟอร์ม, ส่งข้อมูล หรือสุ่มข้อมูลทดสอบ

---

### 2. วิเคราะห์ Google Form เพื่อสร้าง Config และไฟล์ Excel/CSV ต้นแบบ
นำลิงก์ Google Form มาสแกน:
```powershell
python src/main.py parse --url "https://docs.google.com/forms/d/e/1FAIpQLSc.../viewform"
```
สิ่งที่ได้:
- รายชื่อคำถามและ ID ตัวแปรแสดงบนหน้าจอ
- ไฟล์ `config/form_config.yaml`
- ไฟล์ `data/responses_template.csv` สำหรับนำไปเปิดใน Excel แล้วกรอกข้อมูล

---

### 3. ส่งข้อมูลคำตอบจากไฟล์ CSV / Excel

**โหมดที่ 1: Direct HTTP POST (ความเร็วสูง แนะนำสำหรับฟอร์มทั่วไป)**
```powershell
python src/main.py submit --data data/responses.csv --mode direct
```

**โหมดที่ 2: Browser Playwright (เปิดเบราว์เซอร์จริง)**
- รันแบบซ่อนหน้าต่างเบราว์เซอร์ (Headless):
```powershell
python src/main.py submit --data data/responses.csv --mode browser
```
- รันแบบเปิดหน้าต่างให้เห็นการพิมพ์และการคลิก (Headed):
```powershell
python src/main.py submit --data data/responses.csv --mode browser --headed
```

---

### 4. สุ่มสร้างชุดข้อมูลลงไฟล์ CSV ตามเงื่อนไข (Generate Dataset)
ต้องการสุ่มสร้างข้อมูล 100 ชุดลงไฟล์ CSV เพื่อเปิดตรวจดูหรือแก้ไขใน Excel ก่อนส่ง:
```powershell
python src/main.py generate --count 100 --output data/responses.csv
```

---

### 5. สุ่มคำตอบและส่งทันที (Random & Submit Mode)
สุ่มส่งคำตอบจำนวน 300 ชุดผ่านระบบ HTTP POST โดยอิงเงื่อนไขจาก `config/form_config.yaml`:
```powershell
python src/main.py submit --random --count 300 --mode direct
```


---

## 🧪 การทดสอบระบบ (Running Tests)

สามารถรันชุดทดสอบความถูกต้องของโมดูลทั้งหมดได้ด้วยคำสั่ง:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

---

## ⚠️ ข้อควรระวังและคำแนะนำ

1. **ฟอร์มที่บังคับล็อกอินบัญชี Google**:
   - หากฟอร์มมีการตั้งค่า *"จำกัดให้ตอบกลับได้เพียง 1 ครั้ง"* หรือ *"ต้องเข้าสู่ระบบ Google ก่อนตอบ"* จะไม่สามารถใช้โหมด Direct HTTP POST ได้
   - แนะนำให้ใช้โหมด Browser Playwright (`--mode browser --headed`) เพื่อเข้าสู่ระบบบัญชีก่อนทำการส่งคำตอบ
2. **การตั้งหน่วงเวลา (Rate Limit / Delay)**:
   - สามารถปรับค่า `delay_between_requests` ในไฟล์ `config/form_config.yaml` เพื่อป้องกันการถูกจำกัดจากระบบรักษาความปลอดภัยของ Google
