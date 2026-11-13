"""Life Admin Agent demo: track a document expiry date.

Two independent readers extract the expiry date. If they disagree, or the date
is written DD/MM/YYYY (ambiguous), the agent stops and asks the person to
confirm. Files containing injection phrases are quarantined before any reader
runs. The reminder is a draft; "Approve" only logs, nothing is sent.
Grace period (30 days) is a prototype value pending source confirmation.
"""
import io
import re
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

GRACE_DAYS = 30
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+)*(previous|prior|above|earlier)\s+(instructions|rules|prompts?)",
    r"disregard\s+(all\s+|any\s+|the\s+)*(previous|prior|above|earlier)",
    r"(reveal|show|print)\s+(the\s+|your\s+)?system\s+prompt",
    r"\bsystem\s+prompt\b",
    r"rank\s+me\s+(first|number\s+one|#1|at\s+the\s+top)",
    r"you\s+are\s+now\s+(a|an|the)\b",
    r"override\s+(the\s+)?(rules|instructions|safety)",
]
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")  # Arabic-Indic, Persian


def clean(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_DIGITS)


def is_injection(text: str) -> bool:
    t = re.sub(r"\s+", " ", clean(text).lower())
    return any(re.search(p, t) for p in INJECTION_PATTERNS)


def extract_text(name: str, data: bytes) -> str:
    n = name.lower()
    try:
        if n.endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages).strip()
        if n.endswith(".txt"):
            return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
    return ""  # images need OCR, not supported in this demo


def _valid(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def reader_a(text: str):
    """Regex reader: first YYYY-MM-DD in the text, or None."""
    m = re.search(r"\d{4}-\d{2}-\d{2}", clean(text))
    if not m:
        return None
    y, mo, d = map(int, m.group().split("-"))
    return _valid(y, mo, d)


def reader_b(text: str):
    """Label reader: find 'Expiry' and parse the text next to it.
    Returns (raw, fmt, candidates) where fmt is 'ISO', 'DMY' or None."""
    t = clean(text)
    m = re.search(r"expir\w*", t, re.I)
    if not m:
        return None, None, []
    near = t[m.end(): m.end() + 40]
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", near)
    if iso:
        d = _valid(*map(int, iso.groups()))
        return iso.group(), "ISO", [d] if d else []
    dmy = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", near)
    if dmy:
        a, b, y = map(int, dmy.groups())
        cands = []
        for d in (_valid(y, b, a), _valid(y, a, b)):  # DD/MM first, then MM/DD
            if d and d not in cands:
                cands.append(d)
        return dmy.group(), "DMY", cands
    return None, None, []


def analyse(text: str) -> dict:
    """Return status: quarantined | unreadable | agree | confirm, plus the options."""
    if not text:
        return {"status": "unreadable"}
    if is_injection(text):
        return {"status": "quarantined"}
    a = reader_a(text)
    raw_b, fmt_b, cands_b = reader_b(text)
    b = cands_b[0] if (fmt_b == "ISO" and cands_b) else None
    if a and b and a == b:
        return {"status": "agree", "date": a, "a": a, "b": b, "raw_b": raw_b}
    options = []
    for d in ([a] if a else []) + cands_b:
        if d not in options:
            options.append(d)
    if not options:
        return {"status": "unreadable"}
    return {"status": "confirm", "a": a, "b": b, "raw_b": raw_b, "fmt_b": fmt_b, "options": options}


def log(event, detail=""):
    st.session_state.audit.append({"Time": datetime.now().strftime("%H:%M:%S"),
                                   "Event": event, "Detail": detail})


def show_deadline(d: date, key: str):
    grace = d + timedelta(days=GRACE_DAYS)
    st.write("### 3. The Deadline")
    st.info(f"**Expiry:** {d}")
    st.warning(f"**Grace Period Deadline:** {grace} ({GRACE_DAYS} days, prototype value)")
    st.write("### 4. Human Approval Queue")
    st.write(f"Draft reminder: *'Your document expires on {d}. Please renew before {grace}.'*")
    if st.button("Approve Reminder", key="rem_" + key):
        log("Reminder approved", f"{d} (draft only, nothing sent)")
        st.success("Reminder approved and logged. This demo does not send any message.")


def main():
    st.set_page_config(page_title="Life Admin Agent", layout="wide")
    for k, v in (("audit", []), ("logged", set()), ("confirmed", {})):
        if k not in st.session_state:
            st.session_state[k] = v
    st.title("🛂 Life Admin Agent")
    st.markdown("**Demo: Track your UAE document expiries.**")
    st.sidebar.header("Agent Rules")
    st.sidebar.info("1. Files are scanned for injection first.\n2. Two readers extract the date.\n"
                    "3. If they disagree, or the date is DD/MM/YYYY, you confirm.\n"
                    "4. The agent drafts. The human sends.")
    st.sidebar.caption("Files are read in memory and not stored.")

    st.write("### 1. Upload a Document")
    up = st.file_uploader("Upload Visa, Emirates ID, or Passport (text or PDF)", type=["txt", "pdf", "png", "jpg"])
    if up:
        data = up.getvalue()
        key = f"{up.name}_{len(data)}"
        res = analyse(extract_text(up.name, data))
        st.write("### 2. Dual-Reader Extraction")
        once = lambda tag, *a: (key + tag in st.session_state.logged) or (
            st.session_state.logged.add(key + tag), log(*a))

        if res["status"] == "quarantined":
            st.error("🚨 Quarantine Alert: Injection detected. File not read.")
            once("q", "File quarantined", up.name)
        elif res["status"] == "unreadable":
            st.warning("No expiry date could be read (empty file, scan or image). Please enter it manually or upload a text PDF.")
            once("u", "File unreadable", up.name)
        elif res["status"] == "agree":
            st.success(f"**Both readers agree:** Expiry Date is {res['date']}.")
            once("e", "Date extracted", f"{up.name}: A={res['a']} B={res['b']} (agree)")
            show_deadline(res["date"], key)
        else:
            once("e", "Date extracted",
                 f"{up.name}: A={res['a'] or 'none'} B={res['raw_b'] or 'none'} (needs confirmation)")
            chosen = st.session_state.confirmed.get(key)
            if chosen:
                st.success(f"Date confirmed as {chosen}.")
                show_deadline(chosen, key)
            else:
                st.warning("⚠️ **Readers Disagree.** Please confirm the date:")
                st.caption(f"Reader A (regex YYYY-MM-DD): {res['a'] or 'nothing found'} | "
                           f"Reader B (text next to 'Expiry'): {res['raw_b'] or 'nothing found'}")
                cols = st.columns(len(res["options"]))
                for i, (c, d) in enumerate(zip(cols, res["options"])):
                    tag = "Reader A" if d == res["a"] else "Reader B"
                    if c.button(f"Confirm {d} ({tag})", key=f"c{i}_{key}"):
                        st.session_state.confirmed[key] = d
                        log("Date confirmed by user", f"{up.name}: {d}")
                        st.rerun()
    else:
        st.info("Upload a document to start.")

    st.write("---")
    st.write("### Audit log")
    if st.session_state.audit:
        st.dataframe(pd.DataFrame(st.session_state.audit), use_container_width=True, hide_index=True)
    else:
        st.info("No events yet.")


if __name__ == "__main__":
    main()
