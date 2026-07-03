# BigQuery Release Notes Dashboard & Tweet Composer

A modern, responsive dashboard and social sharing tool for Google Cloud BigQuery release notes. This application aggregates the official Google Cloud BigQuery release feed, categorizes individual release items, offers full-text client-side search, and provides a built-in "Tweet Center" widget to draft and share release updates directly to X (formerly Twitter) with a real-time layout preview.

---

## 🚀 Features

- **Automated RSS/Atom Parser**: Regularly fetches, parses, and cleans updates from the official Google Cloud BigQuery Release Notes XML feed.
- **Granular Classification**: Intelligently decomposes single release entries by parsing HTML tags to isolate individual items into categories (e.g., *Features*, *Changes*, *Deprecations*, *Fixes*, *Others*).
- **Fast Client-Side Caching & Refreshing**: Implements server-side caching (10-minute expiry) to limit external API requests, complete with a manual "Force Refresh" control.
- **Interactive Stats Panel**: Visual summary counters mapping count of updates per categories.
- **Keyword Search & Filter Tabs**: Instantly filters releases by keyword matching or category tabs in real time.
- **Built-in Tweet Composer**: Select any release card to auto-generate a draft tweet summarizing the update. Includes:
  - Character counter (warns when exceeding the 280-character limit).
  - Reset function to restore the auto-generated summary template.
  - Realistic Live Preview of the X (Twitter) post card layout.
  - Direct sharing link to X with pre-filled content.
- **Premium Glassmorphism UI**: Stunning modern UI built using a sleek dark mode theme, Google Fonts (`Inter` & `JetBrains Mono`), smooth transitions, pulse animations, and responsive flex/grid layouts.

---

## 🛠️ Technology Stack

- **Backend**:
  - [Python 3](https://www.python.org/)
  - [Flask](https://flask.palletsprojects.com/) (Web routing and API endpoints)
  - [BeautifulSoup 4](https://www.crummy.com/software/BeautifulSoup/) (HTML extraction & tag parser)
  - `xml.etree.ElementTree` (XML parsing)
  - `requests` (Feed retrieval)
- **Frontend**:
  - HTML5 & CSS3 (Custom responsive layout & CSS variables)
  - Vanilla JavaScript (ES6+, DOM manipulation, dynamic API fetching, client-side search/filtering)
  - [FontAwesome](https://fontawesome.com/) (Icon sets)
  - Google Fonts (`Inter`, `JetBrains Mono`)

---

## 📁 Repository Structure

```text
GoogleIntAIAgentsPro/
├── app.py                  # Main Flask application & feed parser logic
├── static/
│   ├── css/
│   │   └── style.css       # Premium responsive styling (dark theme)
│   └── js/
│       └── app.js          # Interactive dashboard logic & Tweet composer
├── templates/
│   └── index.html          # Dashboard HTML skeleton structure
├── .gitignore              # Git ignore rules for Python & environments
└── README.md               # Project documentation
```

---

## ⚙️ Getting Started & Installation

### 1. Prerequisites
- Python 3.8+ installed on your system.
- `pip` package manager.

### 2. Clone the Repository
```bash
git clone https://github.com/Vasper3d2y/KaggleAIAgentsVibeCode.git
cd KaggleAIAgentsVibeCode
```

### 3. Install Dependencies
Create a virtual environment (optional but recommended) and install requirements:
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install Flask requests beautifulsoup4
```

### 4. Run the Application
Start the local Flask development server:
```bash
python3 app.py
```
By default, the server runs on **port 5001** to avoid common system/port conflicts.

Open your browser and navigate to:
```
http://localhost:5001
```

---

## 📝 License

This project is open-source and available under the [MIT License](LICENSE).
