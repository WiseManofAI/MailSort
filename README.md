# MailSort



# MailSort

Anime-themed dashboard for AI-assisted email prioritization.

## Features
- **Train:** Collect samples since a date and label in UI.
- **Process:** Prioritize emails (ML or rules) and move to folders.
- **Recovery:** View LOW-priority emails since date and promote.
- **Stats:** Neon chart for moved counts.

## Setup

1. Create and activate a virtual environment, then install: pip install -r requirement.txt
   
2. Set environment variables (recommended: app-specific password for IMAP):

- Linux/macOS:
  ```bash
  export IMAP_SERVER="imap.gmail.com"
  export EMAIL_USER="your_email@gmail.com"
  export EMAIL_PASS="your_app_password"
  export FOLDER_HIGH="AI_HIGH_PRIORITY"
  export FOLDER_MEDIUM="AI_MEDIUM_PRIORITY"
  export FOLDER_LOW="AI_LOW_PRIORITY_RECOVERY"
  export MODEL_FILE="email_priority_model.pkl"
  export VECTORIZER_FILE="email_vectorizer.pkl"
  export PORT="5000"
  ```

- Windows PowerShell:
  ```powershell
  $env:IMAP_SERVER="imap.gmail.com"
  $env:EMAIL_USER="your_email@gmail.com"
  $env:EMAIL_PASS="your_app_password"
  $env:FOLDER_HIGH="AI_HIGH_PRIORITY"
  $env:FOLDER_MEDIUM="AI_MEDIUM_PRIORITY"
  $env:FOLDER_LOW="AI_LOW_PRIORITY_RECOVERY"
  $env:MODEL_FILE="email_priority_model.pkl"
  $env:VECTORIZER_FILE="email_vectorizer.pkl"
  $env:PORT="5000"


3. Run Backend: python app.py


4. Open frontend:
- Option A: Open `frontend/index.html` directly.  
  Edit `frontend/main.js` to use `http://localhost:5000` for API if needed.
- Option B: Serve `frontend/` on a static server (e.g., `python -m http.server`), keeping same origin.

## Notes
- Use an app-specific IMAP password. [Google Accounts -> App passwords -> Create new (Fill Windows Computer for Windows PC) -> Copy the password in bash or terminal along with your email id]
- Folders are created if missing.
- Model artifacts are saved beside `app.py`.
- Double Factor Authentication must be switched on for that specififc gmail account.
  
  ```


