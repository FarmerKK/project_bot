"""
Unit & Integration Tests for Google Form Bot
"""

import unittest
import os
import json
import tempfile
from src.parser import GoogleFormParser, FormQuestion
from src.data_loader import DataLoader
from src.direct_submitter import DirectSubmitter
from src.browser_submitter import BrowserSubmitter


class TestGoogleFormParser(unittest.TestCase):
    def test_extract_form_id(self):
        url1 = "https://docs.google.com/forms/d/e/1FAIpQLScXyz123456789/viewform"
        self.assertEqual(GoogleFormParser._extract_form_id(url1), "1FAIpQLScXyz123456789")

        url2 = "https://docs.google.com/forms/d/1FAIpQLScXyz123456789/edit"
        self.assertEqual(GoogleFormParser._extract_form_id(url2), "1FAIpQLScXyz123456789")

    def test_parse_fb_public_load_data(self):
        # Simulated Google Forms FB_PUBLIC_LOAD_DATA_ structure
        sample_fb_data = [
            None,
            [
                "แบบสอบถามความพึงพอใจ",
                [
                    [
                        101,
                        "ชื่อ-นามสกุล",
                        "กรุณากรอกชื่อ",
                        0,  # Short answer
                        [[12345678, None, 1]]  # required
                    ],
                    [
                        102,
                        "เพศ",
                        "",
                        2,  # Multiple choice
                        [[87654321, [["ชาย"], ["หญิง"], ["ไม่ระบุ"]], 1]]
                    ],
                    [
                        103,
                        "ความพึงพอใจ",
                        "",
                        5,  # Linear scale
                        [[55555555, [["1"], ["2"], ["3"], ["4"], ["5"]], 0]]
                    ]
                ],
                "คำอธิบายแบบสอบถาม"
            ]
        ]
        html = f"""
        <html>
        <head><title>แบบสอบถาม</title></head>
        <body>
        <script type="text/javascript">
        var FB_PUBLIC_LOAD_DATA_ = {json.dumps(sample_fb_data, ensure_ascii=False)};
        </script>
        </body>
        </html>
        """
        parser = GoogleFormParser("https://docs.google.com/forms/d/e/1FAIpQLSc_TEST/viewform")
        questions = parser._parse_fb_public_load_data(html)

        self.assertEqual(parser.title, "แบบสอบถามความพึงพอใจ")
        self.assertEqual(parser.description, "คำอธิบายแบบสอบถาม")
        self.assertEqual(len(questions), 3)

        self.assertEqual(questions[0].entry_id, "entry.12345678")
        self.assertEqual(questions[0].title, "ชื่อ-นามสกุล")
        self.assertEqual(questions[0].q_type, "Short Answer")
        self.assertTrue(questions[0].required)

        self.assertEqual(questions[1].entry_id, "entry.87654321")
        self.assertEqual(questions[1].options, ["ชาย", "หญิง", "ไม่ระบุ"])

    def test_parse_grid_and_sections(self):
        # Simulated Form with Section Break and Multiple-choice Grid (like user's form)
        sample_fb_data = [
            None,
            [
                "แบบประเมิน Re:Green",
                [
                    # Section 1 questions
                    [
                        1,
                        "ช่วงอายุ",
                        "",
                        2,  # Multiple choice
                        [[10001, [["ต่ำกว่า 15 ปี"], ["15-18 ปี"], ["19-22 ปี"]], 1]]
                    ],
                    # Section 2 break
                    [
                        2,
                        "ตอนที่ 2 ความพึงพอใจ",
                        "",
                        8,  # Page break / Section break
                        None
                    ],
                    # Grid question (type 7)
                    [
                        3,
                        "ระดับความพึงพอใจที่มีต่อเกม",
                        "",
                        7,  # Multiple-choice Grid
                        [
                            [20001, [["5"], ["4"], ["3"], ["2"], ["1"]], 1, ["1. การนำเสนอเนื้อหา"]],
                            [20002, [["5"], ["4"], ["3"], ["2"], ["1"]], 1, ["2. เนื้อหามีความน่าสนใจ"]]
                        ]
                    ]
                ],
                "รายละเอียด"
            ]
        ]
        html = f"""
        <html><body><script>
        var FB_PUBLIC_LOAD_DATA_ = {json.dumps(sample_fb_data, ensure_ascii=False)};
        </script></body></html>
        """
        parser = GoogleFormParser("https://docs.google.com/forms/d/e/1FAIpQLSc_GRID/viewform")
        questions = parser._parse_fb_public_load_data(html)

        self.assertEqual(parser.page_count, 2)
        self.assertEqual(len(questions), 3)

        # First question: Section 1
        self.assertEqual(questions[0].entry_id, "entry.10001")
        self.assertEqual(questions[0].title, "ช่วงอายุ")

        # Second question: Grid Row 1
        self.assertEqual(questions[1].entry_id, "entry.20001")
        self.assertEqual(questions[1].title, "ระดับความพึงพอใจที่มีต่อเกม - 1. การนำเสนอเนื้อหา")
        self.assertEqual(questions[1].options, ["5", "4", "3", "2", "1"])

        # Third question: Grid Row 2
        self.assertEqual(questions[2].entry_id, "entry.20002")
        self.assertEqual(questions[2].title, "ระดับความพึงพอใจที่มีต่อเกม - 2. เนื้อหามีความน่าสนใจ")



class TestDataLoader(unittest.TestCase):
    def test_load_data_with_field_mapping(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write("ชื่อ-นามสกุล,เพศ\n")
            f.write("ทดสอบ บอท,ชาย\n")
            temp_path = f.name

        try:
            mapping = {
                "ชื่อ-นามสกุล": "entry.111111",
                "เพศ": "entry.222222"
            }
            loaded = DataLoader.load_data(temp_path, field_mapping=mapping)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["entry.111111"], "ทดสอบ บอท")
            self.assertEqual(loaded[0]["entry.222222"], "ชาย")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_generate_random_response(self):
        questions = [
            FormQuestion("entry.101", "ชื่อ", "Short Answer", required=True),
            FormQuestion("entry.102", "ระดับ", "Multiple Choice", options=["ระดับ 1", "ระดับ 2"]),
            FormQuestion("entry.103", "วันที่", "Date")
        ]
        resp = DataLoader.generate_random_response(questions)
        self.assertIn("entry.101", resp)
        self.assertIn("entry.102", resp)
        self.assertIn(resp["entry.102"], ["ระดับ 1", "ระดับ 2"])
        self.assertIn("entry.103", resp)


class TestDirectSubmitter(unittest.TestCase):
    def test_prepare_payload(self):
        submitter = DirectSubmitter("https://docs.google.com/forms/d/e/test/formResponse")
        data = {
            "entry.100": "ข้อความตอบ",
            "entry.200": ["ตัวเลือก A", "ตัวเลือก B"],  # Checkbox list
            "ignored_field": "test"
        }
        payload = submitter._prepare_payload(data)
        keys = [p[0] for p in payload]
        values = [p[1] for p in payload]

        self.assertIn("entry.100", keys)
        self.assertEqual(values[keys.index("entry.100")], "ข้อความตอบ")
        self.assertIn("entry.200", keys)
        # Checkbox should yield 2 separate tuples
        count_200 = sum(1 for k in keys if k == "entry.200")
        self.assertEqual(count_200, 2)
        self.assertNotIn("ignored_field", keys)
        self.assertIn("fvv", keys)


if __name__ == "__main__":
    unittest.main()
