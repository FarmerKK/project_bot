"""
Module for extracting question metadata and entry IDs from Google Forms.
Supports automatic parsing via FB_PUBLIC_LOAD_DATA_ and fallback regex/HTML parsing.
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("FormParser")

QUESTION_TYPE_NAMES = {
    0: "Short Answer",
    1: "Paragraph",
    2: "Multiple Choice",
    3: "Dropdown",
    4: "Checkboxes",
    5: "Linear Scale",
    7: "Grid",
    9: "Date",
    10: "Time"
}


class FormQuestion:
    def __init__(
        self,
        entry_id: str,
        title: str,
        q_type: str,
        type_code: Optional[int] = None,
        required: bool = False,
        options: Optional[List[str]] = None,
        description: str = ""
    ):
        self.entry_id = entry_id
        self.title = title
        self.q_type = q_type
        self.type_code = type_code
        self.required = required
        self.options = options or []
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "type": self.q_type,
            "required": self.required,
            "options": self.options,
            "description": self.description
        }


class GoogleFormParser:
    def __init__(self, form_url: str):
        self.raw_url = form_url.strip()
        self.resolved_url = self._resolve_url(self.raw_url)
        self.form_id = self._extract_form_id(self.resolved_url)
        self.view_url = self._build_view_url(self.resolved_url)
        self.response_url = self._build_response_url(self.resolved_url)
        self.title = ""
        self.description = ""
        self.questions: List[FormQuestion] = []
        self.page_count = 1

    @staticmethod
    def _resolve_url(url: str) -> str:
        """Resolve short URLs such as forms.gle/... to final docs.google.com URL."""
        if "forms.gle" in url or "/forms/d/" not in url:
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    allow_redirects=True,
                    timeout=10
                )
                return resp.url
            except Exception:
                pass
        return url

    @staticmethod
    def _extract_form_id(url: str) -> str:
        match = re.search(r'/forms/d/(?:e/)?([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        raise ValueError(f"Cannot extract Google Form ID from URL: {url}")

    def _build_view_url(self, url: str) -> str:
        if "/viewform" in url:
            return url
        base = url.split("?")[0].rstrip("/")
        if not base.endswith("/viewform"):
            if "/forms/d/e/" in base or "/forms/d/" in base:
                return f"{base}/viewform"
        return url

    def _build_response_url(self, url: str) -> str:
        match = re.search(r'(https://docs\.google\.com/forms/d/(?:e/)?[a-zA-Z0-9_-]+)', url)
        if match:
            return f"{match.group(1)}/formResponse"
        return f"https://docs.google.com/forms/d/e/{self.form_id}/formResponse"

    def fetch_and_parse(self, timeout: int = 15) -> List[FormQuestion]:
        """Fetch form HTML and parse all questions."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(self.view_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        html_content = resp.text

        # Try parsing from FB_PUBLIC_LOAD_DATA_
        questions = self._parse_fb_public_load_data(html_content)
        if not questions:
            logger.warning("Could not extract via FB_PUBLIC_LOAD_DATA_, attempting fallback HTML regex...")
            questions = self._parse_fallback_html(html_content)

        self.questions = questions
        return self.questions

    def _parse_fb_public_load_data(self, html: str) -> List[FormQuestion]:
        pattern = r'var\s+FB_PUBLIC_LOAD_DATA_\s*=\s*(.+?);\s*</script>'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            # Another variant pattern
            pattern2 = r'FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.+?\])\s*;'
            match = re.search(pattern2, html, re.DOTALL)
            if not match:
                return []

        try:
            data = json.loads(match.group(1))
        except Exception as e:
            logger.error(f"Failed to decode FB_PUBLIC_LOAD_DATA_ JSON: {e}")
            return []

        # data[1] usually holds [title, items, description, ...]
        if not isinstance(data, list) or len(data) < 2:
            return []

        form_meta = data[1]
        if isinstance(form_meta, list):
            # Check form_meta[8] for true form document title
            if len(form_meta) > 8 and form_meta[8] and isinstance(form_meta[8], str):
                self.title = form_meta[8].strip()
            elif len(form_meta) > 0 and isinstance(form_meta[0], str):
                self.title = form_meta[0].strip()

            if len(form_meta) > 1 and isinstance(form_meta[1], list):
                # Items list
                items = form_meta[1]
            else:
                items = []

            if len(form_meta) > 2 and isinstance(form_meta[2], str):
                self.description = form_meta[2].strip()
        else:
            items = []

        parsed_questions: List[FormQuestion] = []
        page_count = 1

        for item in items:
            if not isinstance(item, list) or len(item) < 4:
                continue

            q_title = item[1] or ""
            q_desc = item[2] or ""
            q_type_code = item[3] if len(item) > 3 else None
            q_type_name = QUESTION_TYPE_NAMES.get(q_type_code, f"Unknown ({q_type_code})")

            # Check if this item is a page break (Section break / ส่วนที่ 2)
            if q_type_code == 8:
                page_count += 1
                continue

            # Check field info in item[4]
            field_data = item[4] if len(item) > 4 and isinstance(item[4], list) else []
            if not field_data:
                continue

            for sub_field in field_data:
                if not isinstance(sub_field, list) or len(sub_field) < 1:
                    continue
                raw_id = sub_field[0]
                if raw_id is None:
                    continue
                entry_id = f"entry.{raw_id}"

                # Extract choices if available
                options = []
                if len(sub_field) > 1 and isinstance(sub_field[1], list):
                    for opt in sub_field[1]:
                        if isinstance(opt, list) and len(opt) > 0 and opt[0]:
                            options.append(str(opt[0]))

                # Extract is_required
                is_req = False
                if len(sub_field) > 2 and sub_field[2] == 1:
                    is_req = True

                # For Grid questions (type 7), extract the row label
                row_label = ""
                if len(sub_field) > 3 and sub_field[3]:
                    if isinstance(sub_field[3], list) and len(sub_field[3]) > 0:
                        row_label = str(sub_field[3][0]).strip()
                    elif isinstance(sub_field[3], str):
                        row_label = sub_field[3].strip()

                if row_label:
                    question_title = f"{q_title} - {row_label}"
                else:
                    question_title = q_title

                parsed_questions.append(
                    FormQuestion(
                        entry_id=entry_id,
                        title=question_title,
                        q_type=q_type_name,
                        type_code=q_type_code,
                        required=is_req,
                        options=options,
                        description=q_desc
                    )
                )

        self.page_count = page_count
        return parsed_questions

    def _parse_fallback_html(self, html: str) -> List[FormQuestion]:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            self.title = title_tag.text.strip()

        # Search for input / textarea with name starting with "entry."
        entries = soup.find_all(["input", "textarea", "select"], attrs={"name": re.compile(r"^entry\.\d+")})
        seen_ids = set()
        questions: List[FormQuestion] = []

        for elem in entries:
            name = elem.get("name")
            if not name or name in seen_ids:
                continue
            seen_ids.add(name)

            # Try finding parent question text
            parent = elem.find_parent("div", role="listitem")
            title = ""
            if parent:
                heading = parent.find(["div", "span"], attrs={"role": "heading"})
                if heading:
                    title = heading.get_text(strip=True)
                else:
                    title = parent.get_text(strip=True)[:50]
            if not title:
                title = f"Question ({name})"

            questions.append(FormQuestion(
                entry_id=name,
                title=title,
                q_type="Standard Input",
                required=False
            ))

        return questions

    def generate_config_template(self) -> Dict[str, Any]:
        """Generate a Python dict ready to dump to YAML."""
        fields_config = {}
        for q in self.questions:
            field_entry = {
                "title": q.title,
                "type": q.q_type,
                "required": q.required,
                "default_value": q.options[0] if q.options else "",
                "options": q.options
            }
            fields_config[q.entry_id] = field_entry

        page_cnt = getattr(self, "page_count", 1)
        page_history = ",".join(str(i) for i in range(page_cnt))

        return {
            "form": {
                "title": self.title,
                "view_url": self.view_url,
                "response_url": self.response_url,
                "mode": "direct",  # direct or browser
                "headless": True,
                "delay_between_requests": 1.0,  # seconds
                "random_delay_range": [0.5, 2.0],
                "page_history": page_history
            },
            "fields": fields_config
        }

