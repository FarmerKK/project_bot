"""
Flask Web Dashboard Backend for Google Form Automation Bot
"""

import sys
import os
import threading
import time
import json
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import parse_qs, urlencode
import yaml
from flask import Flask, render_template, request, jsonify, send_from_directory

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from src.parser import GoogleFormParser
from src.data_loader import DataLoader
from src.direct_submitter import DirectSubmitter
try:
    from src.browser_submitter import BrowserSubmitter
except Exception:
    BrowserSubmitter = None

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static"
)
app.url_map.strict_slashes = False

# Normalize Vercel Serverless rewrites prefix and route parameter in WSGI environ
class VercelPrefixMiddleware(object):
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_str = environ.get('QUERY_STRING', '')
        if '__route' in query_str:
            params = parse_qs(query_str, keep_blank_values=True)
            if '__route' in params and params['__route']:
                route = params.pop('__route')[0]
                if not route.startswith('/'):
                    route = '/' + route
                environ['PATH_INFO'] = route
                environ['QUERY_STRING'] = urlencode(params, doseq=True)
        else:
            path_info = environ.get('PATH_INFO', '')
            for prefix in ['/api/index.py', '/api/index', '/api/app.py', '/api/app']:
                if path_info == prefix:
                    environ['PATH_INFO'] = '/'
                    break
                elif path_info.startswith(prefix + '/'):
                    environ['PATH_INFO'] = path_info[len(prefix):]
                    break
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPrefixMiddleware(app.wsgi_app)

# Global Bot State Controller
class BotState:
    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.total = 0
        self.current = 0
        self.success_count = 0
        self.fail_count = 0
        self.mode = "direct"
        self.logs: List[Dict[str, Any]] = []
        self.thread: Optional[threading.Thread] = None

    def reset(self, total: int, mode: str):
        self.is_running = True
        self.should_stop = False
        self.total = total
        self.current = 0
        self.success_count = 0
        self.fail_count = 0
        self.mode = mode
        self.logs = []

    def add_log(self, text: str, log_type: str = "info"):
        t_str = time.strftime("%H:%M:%S")
        self.logs.append({
            "time": t_str,
            "text": text,
            "type": log_type  # info, success, error, warning
        })
        # Keep last 200 logs
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "total": self.total,
            "current": self.current,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "percent": round((self.current / self.total * 100), 1) if self.total > 0 else 0,
            "mode": self.mode,
            "logs": self.logs[-50:]  # Send latest 50 logs for efficiency
        }

bot_state = BotState()


def is_vercel() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def get_config_path() -> str:
    if is_vercel():
        tmp_path = "/tmp/form_config.yaml"
        if not os.path.exists(tmp_path):
            bundled = os.path.join(BASE_DIR, "config", "form_config.yaml")
            if os.path.exists(bundled):
                try:
                    import shutil
                    os.makedirs("/tmp", exist_ok=True)
                    shutil.copyfile(bundled, tmp_path)
                except Exception:
                    pass
        return tmp_path
    return os.path.join(BASE_DIR, "config", "form_config.yaml")


def get_data_path() -> str:
    if is_vercel():
        tmp_path = "/tmp/responses.csv"
        if not os.path.exists(tmp_path):
            bundled = os.path.join(BASE_DIR, "data", "responses.csv")
            if os.path.exists(bundled):
                try:
                    import shutil
                    os.makedirs("/tmp", exist_ok=True)
                    shutil.copyfile(bundled, tmp_path)
                except Exception:
                    pass
        return tmp_path
    return os.path.join(BASE_DIR, "data", "responses.csv")


def load_config() -> Dict[str, Any]:
    cfg_p = get_config_path()
    if os.path.exists(cfg_p):
        with open(cfg_p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(data: Dict[str, Any]):
    cfg_p = get_config_path()
    try:
        os.makedirs(os.path.dirname(cfg_p), exist_ok=True)
        with open(cfg_p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except OSError:
        fallback_p = "/tmp/form_config.yaml"
        with open(fallback_p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# Routes
@app.route("/")
@app.route("/api/index")
@app.route("/api/index.py")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    for folder in [
        os.path.join(BASE_DIR, "public", "static"),
        os.path.join(BASE_DIR, "static"),
    ]:
        target = os.path.join(folder, filename)
        if os.path.isfile(target):
            return send_from_directory(folder, filename)
    return "Not Found", 404


@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def api_save_config():
    req_data = request.get_json() or {}
    old_cfg = load_config()
    if "conditional_rules" in old_cfg and "conditional_rules" not in req_data:
        req_data["conditional_rules"] = old_cfg["conditional_rules"]
    save_config(req_data)
    return jsonify({"status": "success", "message": "บันทึกการตั้งค่าเรียบร้อยแล้ว"})


@app.route("/api/parse", methods=["POST"])
def api_parse():
    req_data = request.get_json() or {}
    url = req_data.get("url", "").strip()
    if not url:
        return jsonify({"status": "error", "message": "กรุณาระบุ URL"}), 400

    try:
        parser = GoogleFormParser(url)
        questions = parser.fetch_and_parse()
        cfg_data = parser.generate_config_template()
        save_config(cfg_data)

        # Generate template CSV
        DataLoader.create_template_csv(questions, get_data_path(), use_titles_as_header=True)

        return jsonify({
            "status": "success",
            "title": parser.title,
            "description": parser.description,
            "response_url": parser.response_url,
            "page_count": parser.page_count,
            "questions": [q.to_dict() for q in questions]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/generate", methods=["POST"])
def api_generate():
    req_data = request.get_json() or {}
    count = int(req_data.get("count", 100))
    cfg = load_config()
    fields = cfg.get("fields", {})
    cond_rules = cfg.get("conditional_rules", [])

    if not fields:
        return jsonify({"status": "error", "message": "ไม่พบการตั้งค่าฟิลด์คำถาม กรุณาสแกนฟอร์มก่อน"}), 400

    try:
        DataLoader.generate_dataset_csv(fields, count, get_data_path(), conditional_rules=cond_rules)
        return jsonify({"status": "success", "message": f"สุ่มสร้างข้อมูล {count} ชุดเรียบร้อยแล้ว"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/data", methods=["GET"])
def api_get_data():
    data_p = get_data_path()
    if not os.path.exists(data_p):
        return jsonify({"headers": [], "rows": [], "total": 0})

    try:
        import pandas as pd
        df = pd.read_csv(data_p, dtype=str).fillna("")
        headers = list(df.columns)
        # Return first 30 rows for preview
        preview_rows = df.head(30).to_dict(orient="records")
        return jsonify({
            "headers": headers,
            "rows": preview_rows,
            "total": len(df)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def run_bot_worker(mode: str, dataset: List[Dict[str, Any]], delay: float, form_info: Dict[str, Any]):
    bot_state.add_log(f"🚀 เริ่มต้นการทำงานโหมด: {mode.upper()} ทั้งหมด {len(dataset)} ชุด", "info")
    total = len(dataset)

    if mode == "browser":
        submitter = BrowserSubmitter(
            form_url=form_info.get("view_url"),
            headless=True,
            screenshot_dir=os.path.join(BASE_DIR, "logs", "screenshots")
        )
        for i, row in enumerate(dataset, start=1):
            if bot_state.should_stop:
                bot_state.add_log("🛑 ได้รับคำสั่งหยุดการทำงาน", "warning")
                break
            bot_state.current = i
            res = submitter.submit_single(row, index=i)
            if res.success:
                bot_state.success_count += 1
                bot_state.add_log(f"[{i}/{total}] ✔ ส่งสำเร็จ ({res.response_time:.2f}s)", "success")
            else:
                bot_state.fail_count += 1
                bot_state.add_log(f"[{i}/{total}] ✖ ล้มเหลว ({res.error_msg})", "error")
    else:
        # Direct HTTP POST
        page_history = form_info.get("page_history", "0,1")
        submitter = DirectSubmitter(
            response_url=form_info.get("response_url"),
            view_url=form_info.get("view_url"),
            page_history=page_history
        )

        for i, row in enumerate(dataset, start=1):
            if bot_state.should_stop:
                bot_state.add_log("🛑 ได้รับคำสั่งหยุดการทำงาน", "warning")
                break

            bot_state.current = i
            res = submitter.submit_single(row, index=i)
            if res.success:
                bot_state.success_count += 1
                bot_state.add_log(f"[{i}/{total}] ✔ ส่งสำเร็จ (HTTP {res.status_code}, {res.response_time*1000:.0f}ms)", "success")
            else:
                bot_state.fail_count += 1
                bot_state.add_log(f"[{i}/{total}] ✖ ล้มเหลว ({res.error_msg})", "error")

            if i < total and not bot_state.should_stop:
                time.sleep(delay)

    bot_state.is_running = False
    bot_state.add_log(f"🏁 เสร็จสิ้นการทำงาน! สำเร็จ: {bot_state.success_count}/{total}, ล้มเหลว: {bot_state.fail_count}", "info")


@app.route("/api/start", methods=["POST"])
def api_start():
    if bot_state.is_running:
        return jsonify({"status": "error", "message": "บอทกำลังทำงานอยู่แล้ว"}), 400

    req_data = request.get_json() or {}
    mode = req_data.get("mode", "direct")
    delay = float(req_data.get("delay", 0.5))

    if mode == "browser" and BrowserSubmitter is None:
        return jsonify({"status": "error", "message": "โหมด Browser ไม่รองรับบนระบบ Cloud / Vercel กรุณาเลือกโหมด Direct (HTTP)"}), 400

    cfg = load_config()
    form_info = cfg.get("form", {})
    fields = cfg.get("fields", {})
    field_mapping = {val.get("title", ""): entry_id for entry_id, val in fields.items() if val.get("title")}
    options_mapping = {entry_id: f_data.get("options", []) for entry_id, f_data in fields.items() if f_data.get("options")}

    data_p = get_data_path()
    if not os.path.exists(data_p):
        return jsonify({"status": "error", "message": "ไม่พบไฟล์ข้อมูลคำตอบ กรุณาสุ่มสร้างข้อมูลก่อน"}), 400

    dataset = DataLoader.load_data(data_p, field_mapping=field_mapping, options_mapping=options_mapping)
    if not dataset:
        return jsonify({"status": "error", "message": "ไฟล์ข้อมูลว่างเปล่า"}), 400

    bot_state.reset(total=len(dataset), mode=mode)
    thread = threading.Thread(
        target=run_bot_worker,
        args=(mode, dataset, delay, form_info),
        daemon=True
    )
    bot_state.thread = thread
    thread.start()

    return jsonify({"status": "success", "message": "เริ่มต้นส่งคำตอบแล้ว"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not bot_state.is_running:
        return jsonify({"status": "error", "message": "บอทไม่ได้ทำงานอยู่"}), 400

    bot_state.should_stop = True
    return jsonify({"status": "success", "message": "กำลังหยุดการทำงาน..."})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(bot_state.to_dict())


@app.route("/api/env", methods=["GET"])
def api_get_env():
    return jsonify({
        "is_vercel": is_vercel(),
        "has_browser": BrowserSubmitter is not None
    })


@app.route("/api/dataset-all", methods=["GET"])
def api_get_all_dataset():
    data_p = get_data_path()
    if not os.path.exists(data_p):
        return jsonify({"status": "error", "message": "ไม่พบไฟล์ข้อมูลคำตอบ กรุณาสุ่มสร้างข้อมูลก่อน", "dataset": []}), 400

    cfg = load_config()
    fields = cfg.get("fields", {})
    field_mapping = {val.get("title", ""): entry_id for entry_id, val in fields.items() if val.get("title")}
    options_mapping = {entry_id: f_data.get("options", []) for entry_id, f_data in fields.items() if f_data.get("options")}

    dataset = DataLoader.load_data(data_p, field_mapping=field_mapping, options_mapping=options_mapping)
    return jsonify({
        "status": "success",
        "total": len(dataset),
        "dataset": dataset
    })


@app.route("/api/submit-single", methods=["POST"])
def api_submit_single():
    req_data = request.get_json() or {}
    row = req_data.get("row")
    index = int(req_data.get("index", 1))

    if not row:
        return jsonify({"status": "error", "message": "Missing row data"}), 400

    cfg = load_config()
    form_info = cfg.get("form", {})
    page_history = form_info.get("page_history", "0,1")

    submitter = DirectSubmitter(
        response_url=form_info.get("response_url"),
        view_url=form_info.get("view_url"),
        page_history=page_history
    )

    res = submitter.submit_single(row, index=index)
    return jsonify({
        "status": "success" if res.success else "fail",
        "success": res.success,
        "status_code": res.status_code,
        "response_time": round(res.response_time, 3),
        "error_msg": res.error_msg
    })


if __name__ == "__main__":
    print(f"🚀 Starting Web Dashboard at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
