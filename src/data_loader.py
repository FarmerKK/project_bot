"""
Module for loading, mapping, and generating response datasets (CSV, Excel, Config).
"""

import os
import csv
import json
import random
import logging
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger("DataLoader")


class DataLoader:
    @staticmethod
    def load_data(
        file_path: str,
        field_mapping: Optional[Dict[str, str]] = None,
        options_mapping: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Load rows of data from CSV, Excel, or JSON.
        field_mapping: Optional mapping from column header/title -> entry_id (e.g. {"ชื่อ": "entry.1234"})
        options_mapping: Optional mapping from entry_id -> list of valid options
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        rows: List[Dict[str, Any]] = []

        if ext == ".csv":
            df = pd.read_csv(file_path, dtype=str).fillna("")
            rows = df.to_dict(orient="records")
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, dtype=str).fillna("")
            rows = df.to_dict(orient="records")
        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    rows = content
                elif isinstance(content, dict):
                    rows = [content]
        else:
            raise ValueError(f"Unsupported file format: {ext}. Use .csv, .xlsx, or .json")

        # Apply header mapping if provided
        normalized_rows: List[Dict[str, Any]] = []
        for row in rows:
            mapped_row: Dict[str, Any] = {}
            for col_name, value in row.items():
                col_name_str = str(col_name).strip()
                target_key = col_name_str

                # If column is already entry.XXXX, keep it
                if col_name_str.startswith("entry."):
                    target_key = col_name_str
                elif field_mapping and col_name_str in field_mapping:
                    target_key = field_mapping[col_name_str]
                else:
                    # Look for partial or case-insensitive match in mapping
                    if field_mapping:
                        for title, entry_id in field_mapping.items():
                            if title.lower() == col_name_str.lower() or col_name_str.lower() in title.lower() or title.lower() in col_name_str.lower():
                                target_key = entry_id
                                break

                # Normalize value if options_mapping is provided
                val = value
                if options_mapping and target_key in options_mapping:
                    val = DataLoader._normalize_value(value, options_mapping[target_key])

                mapped_row[target_key] = val

            normalized_rows.append(mapped_row)

        return normalized_rows

    @staticmethod
    def _normalize_value(val: Any, options: Optional[List[str]]) -> Any:
        if not options or val is None:
            return val
        val_str = str(val).strip()
        if not val_str:
            return val
        if val_str in options:
            return val_str
        # If user types '5', match '5 มากที่สุด'
        for opt in options:
            first_word = opt.split()[0]
            if first_word == val_str or opt.startswith(val_str):
                return opt
        for opt in options:
            if val_str in opt:
                return opt
        return val

    @staticmethod
    def create_template_csv(
        questions: List[Any],
        output_path: str,
        use_titles_as_header: bool = True
    ) -> None:
        """Generate an empty or sample CSV file based on the form questions."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        headers = []
        sample_row = {}

        for q in questions:
            # Handle FormQuestion object or dict
            if hasattr(q, "entry_id"):
                header = q.title if use_titles_as_header and q.title else q.entry_id
                options = q.options
                q_type = q.q_type
            else:
                header = q.get("title") if use_titles_as_header and q.get("title") else q.get("entry_id")
                options = q.get("options", [])
                q_type = q.get("type", "")

            headers.append(header)
            if options:
                sample_row[header] = options[0]
            elif "Date" in q_type:
                sample_row[header] = "2026-09-12"
            elif "Time" in q_type:
                sample_row[header] = "12:00"
            else:
                sample_row[header] = f"Sample {header}"

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerow(sample_row)

        logger.info(f"Created template CSV at: {output_path}")

    @staticmethod
    def generate_random_response(
        questions: List[Any],
        conditional_rules: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate a single random response payload matching form question options and conditional rules."""
        response = {}
        title_to_id = {}
        for q in questions:
            is_dict = isinstance(q, dict)
            entry_id = q.get("entry_id") if is_dict else getattr(q, "entry_id", "")
            title = q.get("title", "") if is_dict else getattr(q, "title", "")
            if title:
                title_to_id[title] = entry_id
            options = q.get("options", []) if is_dict else getattr(q, "options", [])
            weights = q.get("weights", None) if is_dict else getattr(q, "weights", None)
            q_type = q.get("type", "") if is_dict else getattr(q, "q_type", "")

            if options:
                if weights and len(weights) == len(options):
                    try:
                        num_weights = [float(w) for w in weights]
                        if sum(num_weights) > 0:
                            response[entry_id] = random.choices(options, weights=num_weights, k=1)[0]
                        else:
                            response[entry_id] = random.choice(options)
                    except Exception:
                        response[entry_id] = random.choice(options)
                else:
                    response[entry_id] = random.choice(options)
            elif "Date" in q_type:
                y = random.randint(2023, 2026)
                m = f"{random.randint(1, 12):02d}"
                d = f"{random.randint(1, 28):02d}"
                response[entry_id] = f"{y}-{m}-{d}"
            elif "Time" in q_type:
                h = f"{random.randint(8, 20):02d}"
                mi = f"{random.randint(0, 59):02d}"
                response[entry_id] = f"{h}:{mi}"
            else:
                dummy_words = ["ดีเยี่ยม", "เรียบร้อย", "เห็นด้วย", "ทดสอบระบบ", "ข้อมูลถูกต้อง"]
                response[entry_id] = random.choice(dummy_words)

        # Apply conditional rules if provided
        if conditional_rules:
            def norm_text(s):
                return str(s).replace("–", "-").replace("—", "-").strip() if s is not None else ""

            def resolve_key(name):
                if not name:
                    return ""
                if name in title_to_id:
                    return title_to_id[name]
                norm_name = norm_text(name).lower()
                for t, eid in title_to_id.items():
                    norm_t = norm_text(t).lower()
                    if norm_name == norm_t or norm_name in norm_t or norm_t in norm_name:
                        return eid
                return name

            for rule in conditional_rules:
                if not rule.get("enabled", True):
                    continue

                if_field = rule.get("if_field", "")
                if_key = resolve_key(if_field)
                if_val = response.get(if_key)

                if_in = rule.get("if_in", [])
                if isinstance(if_in, str):
                    if_in = [if_in]

                norm_val = norm_text(if_val)
                norm_options = [norm_text(opt) for opt in if_in]

                matched = (
                    if_val in if_in or
                    norm_val in norm_options or
                    any(norm_val == o or (norm_val and (norm_val in o or o in norm_val)) for o in norm_options)
                )

                if matched:
                    then_field = rule.get("then_field", "")
                    then_key = resolve_key(then_field)
                    then_set = rule.get("then_set")
                    if isinstance(then_set, list):
                        if then_set:
                            response[then_key] = random.choice(then_set)
                    elif then_set is not None:
                        response[then_key] = str(then_set)

        return response

    @staticmethod
    def generate_dataset_csv(
        fields_config: Dict[str, Any],
        count: int,
        output_path: str,
        conditional_rules: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Generate a synthetic dataset of `count` rows and save to CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        questions_list = []
        headers = []
        for entry_id, f_data in fields_config.items():
            title = f_data.get("title", entry_id)
            headers.append(title)
            questions_list.append({
                "entry_id": entry_id,
                "title": title,
                "type": f_data.get("type", ""),
                "options": f_data.get("options", []),
                "weights": f_data.get("weights", None)
            })

        dataset = []
        rows_for_csv = []
        for _ in range(count):
            row_dict = DataLoader.generate_random_response(questions_list, conditional_rules=conditional_rules)
            dataset.append(row_dict)

            # Map entry.XXXX to title for human-readable CSV
            csv_row = {}
            for entry_id, val in row_dict.items():
                title = fields_config.get(entry_id, {}).get("title", entry_id)
                csv_row[title] = val
            rows_for_csv.append(csv_row)

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows_for_csv)

        logger.info(f"Generated {count} rows to {output_path}")
        return dataset


