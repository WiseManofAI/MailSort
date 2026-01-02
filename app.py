# app.py
import os
import re
import email
import imaplib
import joblib
import datetime
from email.header import decode_header
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ---- Configuration via environment variables ----
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")

FOLDERS = {
    "HIGH": os.getenv("FOLDER_HIGH", "AI_HIGH_PRIORITY"),
    "MEDIUM": os.getenv("FOLDER_MEDIUM", "AI_MEDIUM_PRIORITY"),
    "LOW": os.getenv("FOLDER_LOW", "AI_LOW_PRIORITY_RECOVERY"),
}

MODEL_FILE = os.getenv("MODEL_FILE", "email_priority_model.pkl")
VECTORIZER_FILE = os.getenv("VECTORIZER_FILE", "email_vectorizer.pkl")

# ---- Rule-based fallback ----
URGENT_KEYWORDS = ["urgent", "asap", "deadline", "action required"]
SERVICE_KEYWORDS = ["invoice", "meeting", "support", "request"]
LOW_PRIORITY_KEYWORDS = ["offer", "sale", "newsletter", "unsubscribe"]

# ---- Utils ----
def clean_text(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

def summarize(text, max_sentences=2):
    sentences = text.replace("\n", " ").split(". ")
    return ". ".join(sentences[:max_sentences])

def rule_based_rank(text):
    score = 0
    t = clean_text(text)
    for w in URGENT_KEYWORDS:
        if w in t:
            score += 3
    for w in SERVICE_KEYWORDS:
        if w in t:
            score += 2
    for w in LOW_PRIORITY_KEYWORDS:
        if w in t:
            score -= 3
    if score >= 3:
        return "HIGH"
    elif score >= 1:
        return "MEDIUM"
    return "LOW"

def generate_gmail_link(email_id_bytes):
    try:
        return f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{email_id_bytes.decode()}"
    except Exception:
        return ""

def load_or_init_model():
    if os.path.exists(MODEL_FILE) and os.path.exists(VECTORIZER_FILE):
        model = joblib.load(MODEL_FILE)
        vectorizer = joblib.load(VECTORIZER_FILE)
        return model, vectorizer, True
    model = LogisticRegression(max_iter=1000)
    vectorizer = TfidfVectorizer(stop_words="english")
    return model, vectorizer, False

def connect_mail():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("INBOX")
    # Ensure folders exist
    for folder in FOLDERS.values():
        try:
            mail.create(folder)
        except:
            pass
    return mail

def parse_email(message):
    subject_raw = message.get("Subject") or "(No Subject)"
    subject, encoding = decode_header(subject_raw)[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8", errors="ignore")

    body = ""
    if message.is_multipart():
        for part in message.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                body = (part.get_payload(decode=True) or b"").decode(errors="ignore")
                break
            elif ctype == "text/html":
                html = (part.get_payload(decode=True) or b"").decode(errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                body = soup.get_text()
    else:
        body = (message.get_payload(decode=True) or b"").decode(errors="ignore")

    return subject, body

# ---- Flask app ----
app = Flask(__name__)

@app.route("/api/train", methods=["POST"])
def api_train():
    """
    Collect samples for labeling since date.
    Payload: { "start_date": "YYYY-MM-DD", "limit": 10 }
    """
    data = request.get_json(force=True)
    start_date_str = data.get("start_date")
    limit = int(data.get("limit", 0))
    if not start_date_str or limit <= 0:
        return jsonify({"error": "Provide start_date and positive limit"}), 400

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid start_date format"}), 400

    model, vectorizer, ml_ready = load_or_init_model()
    mail = connect_mail()

    imap_date = start_date.strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'SINCE {imap_date}')
    email_ids = messages[0].split()

    trained_count = 0
    samples = []

    for email_id in email_ids:
        if trained_count >= limit:
            break
        res, msg = mail.fetch(email_id, "(RFC822)")
        raw_email = msg[0][1]
        message = email.message_from_bytes(raw_email)

        subject, body = parse_email(message)
        full_text = clean_text(subject + " " + body)
        summary = summarize(full_text)

        samples.append({
            "email_id": email_id.decode(),
            "subject": subject,
            "summary": summary
        })
        trained_count += 1

    mail.logout()
    return jsonify({
        "ml_ready": ml_ready,
        "samples": samples,
        "message": f"Collected {trained_count} samples for labeling"
    })

@app.route("/api/label", methods=["POST"])
def api_label():
    """
    Accept labels and train/save model.
    Payload: { "items": [ { "email_id": "...", "subject": "...", "summary": "...", "label": "HIGH|MEDIUM|LOW" } ] }
    """
    data = request.get_json(force=True)
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "No items provided"}), 400

    model, vectorizer, ml_ready = load_or_init_model()

    texts = []
    labels = []
    for it in items:
        label = it.get("label", "").upper()
        if label not in ["HIGH", "MEDIUM", "LOW"]:
            continue
        text = clean_text(f"{it.get('subject','')} {it.get('summary','')}")
        texts.append(text)
        labels.append(label)

    if not texts:
        return jsonify({"error": "No valid labels"}), 400

    X = vectorizer.fit_transform(texts)
    model.fit(X, labels)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(vectorizer, VECTORIZER_FILE)

    return jsonify({"ml_ready": True, "message": "Model trained and saved"})

@app.route("/api/process", methods=["POST"])
def api_process():
    """
    Process emails since date.
    Payload: { "start_date": "YYYY-MM-DD" }
    """
    data = request.get_json(force=True)
    start_date_str = data.get("start_date")
    if not start_date_str:
        return jsonify({"error": "Provide start_date"}), 400

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid start_date format"}), 400

    model, vectorizer, ml_ready = load_or_init_model()
    mail = connect_mail()

    imap_date = start_date.strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'SINCE {imap_date}')
    email_ids = messages[0].split()

    results = []
    moved_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for email_id in email_ids:
        res, msg = mail.fetch(email_id, "(RFC822)")
        raw_email = msg[0][1]
        message = email.message_from_bytes(raw_email)

        subject, body = parse_email(message)
        full_text = clean_text(subject + " " + body)
        summary = summarize(full_text)
        gmail_link = generate_gmail_link(email_id)

        if ml_ready:
            X = vectorizer.transform([full_text])
            priority = model.predict(X)[0]
        else:
            priority = rule_based_rank(full_text)

        if priority in ("HIGH", "MEDIUM"):
            mail.copy(email_id, FOLDERS[priority])
            mail.store(email_id, "+FLAGS", "\\Seen")
        else:
            mail.copy(email_id, FOLDERS["LOW"])
            mail.store(email_id, "+FLAGS", "\\Seen")

        moved_counts[priority] += 1
        results.append({
            "subject": subject,
            "summary": summary,
            "priority": priority,
            "gmail_link": gmail_link
        })

    mail.expunge()
    mail.logout()

    return jsonify({
        "ml_ready": ml_ready,
        "moved_counts": moved_counts,
        "items": results
    })

@app.route("/api/recovery", methods=["POST"])
def api_recovery():
    """
    List recovery emails since date.
    Payload: { "start_date": "YYYY-MM-DD" }
    """
    data = request.get_json(force=True)
    start_date_str = data.get("start_date")
    if not start_date_str:
        return jsonify({"error": "Provide start_date"}), 400

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid start_date format"}), 400

    mail = connect_mail()
    mail.select(FOLDERS["LOW"])
    imap_date = start_date.strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'SINCE {imap_date}')
    email_ids = messages[0].split()

    items = []
    for email_id in email_ids:
        res, msg = mail.fetch(email_id, "(RFC822)")
        raw_email = msg[0][1]
        message = email.message_from_bytes(raw_email)

        subject, body = parse_email(message)
        full_text = clean_text(subject + " " + body)
        summary = summarize(full_text)
        gmail_link = generate_gmail_link(email_id)

        items.append({
            "email_id": email_id.decode(),
            "subject": subject,
            "summary": summary,
            "gmail_link": gmail_link
        })

    mail.logout()
    return jsonify({"items": items})

@app.route("/api/promote", methods=["POST"])
def api_promote():
    """
    Promote an email from recovery to HIGH or MEDIUM.
    Payload: { "email_id": "<id>", "new_priority": "HIGH|MEDIUM" }
    """
    data = request.get_json(force=True)
    email_id_str = data.get("email_id")
    new_priority = data.get("new_priority", "").upper()
    if not email_id_str or new_priority not in ["HIGH", "MEDIUM"]:
        return jsonify({"error": "Provide email_id and valid new_priority"}), 400

    mail = connect_mail()
    mail.select(FOLDERS["LOW"])
    try:
        mail.copy(email_id_str, FOLDERS[new_priority])
        mail.store(email_id_str, "+FLAGS", "\\Deleted")
        mail.expunge()
    except Exception as e:
        mail.logout()
        return jsonify({"error": f"Promotion failed: {e}"}), 500

    mail.logout()
    return jsonify({"message": f"Email promoted to {new_priority}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
