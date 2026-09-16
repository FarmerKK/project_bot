"""
Module for submitting Google Form responses directly via HTTP POST requests.
Fastest mode, doesn't require opening a browser.
"""

import time
import random
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import requests

logger = logging.getLogger("DirectSubmitter")


class SubmissionResult:
    def __init__(
        self,
        index: int,
        success: bool,
        status_code: int,
        response_time: float,
        error_msg: str = "",
        payload: Optional[Dict[str, Any]] = None
    ):
        self.index = index
        self.success = success
        self.status_code = status_code
        self.response_time = response_time
        self.error_msg = error_msg
        self.payload = payload or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "success": self.success,
            "status_code": self.status_code,
            "response_time_ms": round(self.response_time * 1000, 2),
            "error_msg": self.error_msg
        }


class DirectSubmitter:
    def __init__(
        self,
        response_url: str,
        view_url: Optional[str] = None,
        page_history: str = "0,1",
        timeout: int = 15,
        session: Optional[requests.Session] = None
    ):
        self.response_url = response_url
        self.view_url = view_url or response_url.replace("/formResponse", "/viewform")
        self.page_history = page_history
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": self.view_url,
            "Origin": "https://docs.google.com"
        })

    def _prepare_payload(self, data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """
        Convert dict to list of tuples to support multiple values for the same entry ID (e.g. Checkboxes).
        """
        payload: List[Tuple[str, str]] = []
        for key, val in data.items():
            if not key.startswith("entry."):
                continue

            if isinstance(val, (list, tuple)):
                for item in val:
                    if item is not None and str(item).strip():
                        payload.append((key, str(item).strip()))
            else:
                if val is not None:
                    payload.append((key, str(val).strip()))

        # Google Form standard submission parameters
        payload.append(("fvv", "1"))
        payload.append(("draftResponse", "[]"))
        payload.append(("pageHistory", self.page_history))
        payload.append(("fbzx", ""))
        return payload

    def submit_single(self, data: Dict[str, Any], index: int = 1) -> SubmissionResult:
        """Submit a single response to Google Form."""
        payload_tuples = self._prepare_payload(data)
        start_t = time.time()

        try:
            resp = self.session.post(
                self.response_url,
                data=payload_tuples,
                timeout=self.timeout,
                allow_redirects=True
            )
            elapsed = time.time() - start_t

            # Check if submission was accepted
            # Google Form returns 200 OK with confirmation text in HTML
            is_success = resp.status_code == 200 and (
                "formResponse" in resp.url or
                "Your response has been recorded" in resp.text or
                "เราได้บันทึกคำตอบของคุณไว้แล้ว" in resp.text or
                "freebirdFormviewerViewResponseConfirmationMessage" in resp.text
            )

            if is_success:
                return SubmissionResult(
                    index=index,
                    success=True,
                    status_code=resp.status_code,
                    response_time=elapsed,
                    payload=data
                )
            else:
                err = f"Submission returned status {resp.status_code}, might be rejected or required sign-in."
                logger.warning(f"[{index}] {err}")
                return SubmissionResult(
                    index=index,
                    success=False,
                    status_code=resp.status_code,
                    response_time=elapsed,
                    error_msg=err,
                    payload=data
                )

        except requests.RequestException as e:
            elapsed = time.time() - start_t
            err = f"Request error: {str(e)}"
            logger.error(f"[{index}] {err}")
            return SubmissionResult(
                index=index,
                success=False,
                status_code=0,
                response_time=elapsed,
                error_msg=err,
                payload=data
            )

    def submit_batch(
        self,
        dataset: List[Dict[str, Any]],
        delay: float = 1.0,
        random_delay_range: Optional[Tuple[float, float]] = None,
        progress_callback: Optional[Any] = None
    ) -> List[SubmissionResult]:
        """Submit multiple responses in sequence with configurable delay."""
        results: List[SubmissionResult] = []
        total = len(dataset)

        for i, row in enumerate(dataset, start=1):
            res = self.submit_single(row, index=i)
            results.append(res)

            if progress_callback:
                progress_callback(i, total, res)

            # Delay before next request (except for the last one)
            if i < total:
                if random_delay_range:
                    sleep_sec = random.uniform(*random_delay_range)
                else:
                    sleep_sec = delay
                time.sleep(sleep_sec)

        return results
