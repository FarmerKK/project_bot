"""
Google Form Automation Bot - Main CLI & Controller
"""

import sys
import os
import argparse
import logging
import yaml
from colorama import init, Fore, Style

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Initialize colorama for Windows terminal
init(autoreset=True)

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import GoogleFormParser
from src.data_loader import DataLoader
from src.direct_submitter import DirectSubmitter
from src.browser_submitter import BrowserSubmitter

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/submission.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MainBot")


def print_banner():
    print(Fore.CYAN + Style.BRIGHT + """
======================================================
    🤖 Google Form Automation Bot v1.0
    ⚡ Fast HTTP POST & 🌐 Playwright Browser
======================================================
""" + Style.RESET_ALL)


def handle_parse(url: str, output_config: str = "config/form_config.yaml", output_csv: str = "data/responses_template.csv"):
    print(f"\n🔍 กำลังวิเคราะห์ Google Form: {Fore.YELLOW}{url}{Style.RESET_ALL}")
    parser = GoogleFormParser(url)
    try:
        questions = parser.fetch_and_parse()
    except Exception as e:
        print(f"{Fore.RED}❌ เกิดข้อผิดพลาดในการโหลดฟอร์ม: {e}{Style.RESET_ALL}")
        return None

    print(f"\n{Fore.GREEN}✔ โหลดฟอร์มสำเร็จ!{Style.RESET_ALL}")
    print(f"📌 {Style.BRIGHT}หัวข้อฟอร์ม:{Style.RESET_ALL} {parser.title or '(ไม่มีชื่อ)'}")
    if parser.description:
        print(f"📝 {Style.BRIGHT}รายละเอียด:{Style.RESET_ALL} {parser.description}")
    print(f"🔗 {Style.BRIGHT}Response URL:{Style.RESET_ALL} {parser.response_url}\n")

    print(f"{Style.BRIGHT}{'#':<4} {'Entry ID':<18} {'ประเภท':<18} {'จำเป็น':<8} {'คำถาม'}{Style.RESET_ALL}")
    print("-" * 75)
    for i, q in enumerate(questions, start=1):
        req_mark = f"{Fore.RED}ใช่{Style.RESET_ALL}" if q.required else f"{Fore.WHITE}ไม่{Style.RESET_ALL}"
        print(f"{i:<4} {Fore.CYAN}{q.entry_id:<18}{Style.RESET_ALL} {q.q_type:<18} {req_mark:<8} {q.title}")
        if q.options:
            opts_str = ", ".join(q.options[:5])
            if len(q.options) > 5:
                opts_str += f" ... (ทั้งหมด {len(q.options)} ตัวเลือก)"
            print(f"     └─ ตัวเลือก: {Fore.LIGHTBLACK_EX}{opts_str}{Style.RESET_ALL}")

    # Generate config YAML
    os.makedirs(os.path.dirname(output_config), exist_ok=True)
    cfg_data = parser.generate_config_template()
    with open(output_config, "w", encoding="utf-8") as f:
        yaml.dump(cfg_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\n💾 {Fore.GREEN}สร้างไฟล์การตั้งค่าแล้ว:{Style.RESET_ALL} {output_config}")

    # Generate CSV template
    DataLoader.create_template_csv(questions, output_csv, use_titles_as_header=True)
    print(f"📄 {Fore.GREEN}สร้างไฟล์ต้นแบบ CSV แล้ว:{Style.RESET_ALL} {output_csv}")

    return parser


def handle_submit(
    config_path: str = "config/form_config.yaml",
    data_path: str = "data/responses.csv",
    mode: str = "direct",
    count: int = 1,
    random_mode: bool = False,
    headless: bool = True
):
    if not os.path.exists(config_path):
        print(f"{Fore.RED}❌ ไม่พบไฟล์คอนฟิก: {config_path}{Style.RESET_ALL}")
        print("กรุณาสั่งรันคำสั่ง parse ก่อนเพื่อสร้างคอนฟิก เช่น: python src/main.py parse --url <URL>")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    form_info = config.get("form", {})
    response_url = form_info.get("response_url")
    view_url = form_info.get("view_url")
    selected_mode = mode or form_info.get("mode", "direct")
    fields = config.get("fields", {})

    # Build field mapping (Question Title -> entry.XXXX)
    field_mapping = {val.get("title", ""): entry_id for entry_id, val in fields.items() if val.get("title")}

    # Prepare dataset
    dataset = []
    if random_mode:
        print(f"\n🎲 {Fore.MAGENTA}โหมดสุ่มคำตอบอัตโนมัติ (จำนวน {count} ชุด){Style.RESET_ALL}")
        questions_list = []
        for entry_id, f_data in fields.items():
            questions_list.append({
                "entry_id": entry_id,
                "title": f_data.get("title", ""),
                "type": f_data.get("type", ""),
                "options": f_data.get("options", []),
                "weights": f_data.get("weights", None)
            })
        conditional_rules = config.get("conditional_rules", [])
        for _ in range(count):
            dataset.append(DataLoader.generate_random_response(questions_list, conditional_rules=conditional_rules))
    else:
        if os.path.exists(data_path):
            print(f"\n📂 กำลังโหลดข้อมูลจาก: {Fore.YELLOW}{data_path}{Style.RESET_ALL}")
            options_mapping = {entry_id: f_data.get("options", []) for entry_id, f_data in fields.items() if f_data.get("options")}
            dataset = DataLoader.load_data(data_path, field_mapping=field_mapping, options_mapping=options_mapping)
            print(f"📊 โหลดข้อมูลได้ทั้งหมด {Fore.GREEN}{len(dataset)}{Style.RESET_ALL} แถว")
        else:
            print(f"{Fore.YELLOW}⚠ ไม่พบไฟล์ข้อมูล {data_path} - ใช้ข้อมูลเริ่มต้นจาก config{Style.RESET_ALL}")
            default_row = {entry_id: f_data.get("default_value", "") for entry_id, f_data in fields.items()}
            dataset = [default_row] * count

    if not dataset:
        print(f"{Fore.RED}❌ ไม่มีข้อมูลสำหรับส่งคำตอบ{Style.RESET_ALL}")
        return

    total = len(dataset)
    print(f"\n🚀 {Style.BRIGHT}เริ่มต้นการส่งข้อมูล (โหมด: {selected_mode.upper()}, ทั้งหมด: {total} ชุด)...{Style.RESET_ALL}\n")

    success_count = 0
    fail_count = 0

    if selected_mode == "browser":
        # Browser Automation via Playwright
        submitter = BrowserSubmitter(
            form_url=view_url,
            headless=headless,
            screenshot_dir="logs/screenshots"
        )
        for i, row in enumerate(dataset, start=1):
            print(f"[{i}/{total}] กำลังเปิดเบราว์เซอร์และกรอกข้อมูล... ", end="", flush=True)
            res = submitter.submit_single(row, index=i)
            if res.success:
                print(f"{Fore.GREEN}✔ สำเร็จ{Style.RESET_ALL} ({res.response_time:.2f}s)")
                success_count += 1
            else:
                print(f"{Fore.RED}✖ ล้มเหลว{Style.RESET_ALL} ({res.error_msg})")
                fail_count += 1
    else:
        # Direct HTTP POST
        page_history = form_info.get("page_history", "0,1")
        submitter = DirectSubmitter(
            response_url=response_url,
            view_url=view_url,
            page_history=page_history
        )

        def progress_cb(current, total_items, res):
            nonlocal success_count, fail_count
            if res.success:
                print(f"[{current}/{total_items}] {Fore.GREEN}✔ ส่งสำเร็จ{Style.RESET_ALL} (HTTP {res.status_code}, {res.response_time*1000:.0f}ms)")
                success_count += 1
            else:
                print(f"[{current}/{total_items}] {Fore.RED}✖ ล้มเหลว{Style.RESET_ALL} (HTTP {res.status_code}, {res.error_msg})")
                fail_count += 1

        delay = form_info.get("delay_between_requests", 1.0)
        submitter.submit_batch(
            dataset=dataset,
            delay=delay,
            progress_callback=progress_cb
        )

    print("\n" + "=" * 50)
    print(f"{Style.BRIGHT}📊 สรุปผลการส่งคำตอบ:{Style.RESET_ALL}")
    print(f"  - สำเร็จ: {Fore.GREEN}{success_count}{Style.RESET_ALL} / {total}")
    print(f"  - ล้มเหลว: {Fore.RED}{fail_count}{Style.RESET_ALL} / {total}")
    print(f"  - ตรวจสอบบันทึกละเอียดได้ที่: logs/submission.log")
    print("=" * 50 + "\n")


def handle_generate(
    config_path: str = "config/form_config.yaml",
    count: int = 100,
    output_csv: str = "data/responses.csv"
):
    if not os.path.exists(config_path):
        print(f"{Fore.RED}❌ ไม่พบไฟล์คอนฟิก: {config_path}{Style.RESET_ALL}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fields = config.get("fields", {})
    conditional_rules = config.get("conditional_rules", [])
    print(f"\n🎲 กำลังสุ่มสร้างชุดข้อมูลจำนวน {Fore.GREEN}{count}{Style.RESET_ALL} ชุด ตามเงื่อนไขใน {config_path}...")
    DataLoader.generate_dataset_csv(fields, count, output_csv, conditional_rules=conditional_rules)
    print(f"📄 {Fore.GREEN}✔ สร้างไฟล์ข้อมูลเรียบร้อยแล้ว:{Style.RESET_ALL} {output_csv}")
    print(f"คุณสามารถเปิดตรวจดูใน Excel หรือสั่งส่งได้ทันทีด้วยคำสั่ง: python src/main.py submit --data {output_csv}\n")


def interactive_menu():
    print_banner()
    while True:
        print("\nกรุณาเลือกเมนูการทำงาน:")
        print("1. 🔍 วิเคราะห์ Google Form และสร้างไฟล์คอนฟิก (Parse Form)")
        print("2. 🚀 ส่งคำตอบจากไฟล์ข้อมูล (CSV / Excel)")
        print("3. 🎲 สุ่มคำตอบและส่งทันที (Random & Submit)")
        print("4. 📝 สุ่มสร้างชุดข้อมูลลงไฟล์ CSV เพื่อตรวจดูก่อน (Generate CSV)")
        print("5. 🚪 ออกจากโปรแกรม (Exit)")

        choice = input(Fore.YELLOW + "\nเลือกหมายเลข (1-5): " + Style.RESET_ALL).strip()

        if choice == "1":
            url = input("กรุณาวางลิงก์ Google Form: ").strip()
            if url:
                handle_parse(url)
            else:
                print(Fore.RED + "URL ไม่ถูกต้อง" + Style.RESET_ALL)
        elif choice == "2":
            mode_input = input("เลือกโหมด [1: Direct HTTP (เร็ว), 2: Browser Playwright] (ค่าเริ่มต้น 1): ").strip()
            mode = "browser" if mode_input == "2" else "direct"
            data_file = input("ระบุเส้นทางไฟล์ข้อมูล (ค่าเริ่มต้น data/responses.csv): ").strip() or "data/responses.csv"
            headless = True
            if mode == "browser":
                head_inp = input("ต้องการเปิดดูหน้าจอเบราว์เซอร์หรือไม่? (y/n, ค่าเริ่มต้น n): ").strip().lower()
                headless = head_inp != "y"
            handle_submit(data_path=data_file, mode=mode, headless=headless)
        elif choice == "3":
            count_str = input("ต้องการส่งกี่ชุด? (ค่าเริ่มต้น 1): ").strip() or "1"
            try:
                count = int(count_str)
            except ValueError:
                count = 1
            mode_input = input("เลือกโหมด [1: Direct HTTP (เร็ว), 2: Browser Playwright] (ค่าเริ่มต้น 1): ").strip()
            mode = "browser" if mode_input == "2" else "direct"
            handle_submit(mode=mode, count=count, random_mode=True)
        elif choice == "4":
            count_str = input("ต้องการสร้างข้อมูลกี่ชุด? (ค่าเริ่มต้น 100): ").strip() or "100"
            try:
                count = int(count_str)
            except ValueError:
                count = 100
            out_file = input("บันทึกลงไฟล์ (ค่าเริ่มต้น data/responses.csv): ").strip() or "data/responses.csv"
            handle_generate(count=count, output_csv=out_file)
        elif choice == "5":
            print(Fore.CYAN + "👋 ลาก่อน ขอให้มีความสุขกับการใช้งาน!" + Style.RESET_ALL)
            break
        else:
            print(Fore.RED + "ตัวเลือกไม่ถูกต้อง กรุณาเลือกใหม่" + Style.RESET_ALL)


def main():
    parser = argparse.ArgumentParser(description="Google Form Automation Bot")
    subparsers = parser.add_subparsers(dest="command")

    # Command: parse
    parse_cmd = subparsers.add_parser("parse", help="Parse Google Form and export questions/entry IDs")
    parse_cmd.add_argument("--url", required=True, help="Google Form public URL")
    parse_cmd.add_argument("--config", default="config/form_config.yaml", help="Output YAML config path")
    parse_cmd.add_argument("--csv", default="data/responses_template.csv", help="Output CSV template path")

    # Command: generate
    gen_cmd = subparsers.add_parser("generate", help="Generate synthetic CSV dataset matching config")
    gen_cmd.add_argument("--config", default="config/form_config.yaml", help="Path to config YAML")
    gen_cmd.add_argument("--count", type=int, default=100, help="Number of responses to generate")
    gen_cmd.add_argument("--output", default="data/responses.csv", help="Output CSV path")

    # Command: submit
    submit_cmd = subparsers.add_parser("submit", help="Submit responses to Google Form")
    submit_cmd.add_argument("--config", default="config/form_config.yaml", help="Path to config YAML")
    submit_cmd.add_argument("--data", default="data/responses.csv", help="Path to CSV or Excel data file")
    submit_cmd.add_argument("--mode", choices=["direct", "browser"], default="direct", help="Submission mode")
    submit_cmd.add_argument("--count", type=int, default=1, help="Number of submissions")
    submit_cmd.add_argument("--random", action="store_true", help="Generate random responses matching form options")
    submit_cmd.add_argument("--headed", action="store_true", help="Run browser in visible mode (Playwright)")

    args = parser.parse_args()

    if args.command == "parse":
        print_banner()
        handle_parse(args.url, args.config, args.csv)
    elif args.command == "generate":
        print_banner()
        handle_generate(args.config, args.count, args.output)
    elif args.command == "submit":
        print_banner()
        handle_submit(
            config_path=args.config,
            data_path=args.data,
            mode=args.mode,
            count=args.count,
            random_mode=args.random,
            headless=not args.headed
        )
    else:
        # If no arguments provided, launch interactive menu
        interactive_menu()


if __name__ == "__main__":
    main()

