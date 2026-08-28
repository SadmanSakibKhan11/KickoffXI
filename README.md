# ⚽ KickoffXI — FIFA World Cup 2026 Player Database

A full-featured web application for browsing and searching every player in the **FIFA World Cup 2026** tournament. Built with **Flask** and powered by CSV-based data, the app provides a fast, searchable player database with a modern, responsive UI.

---

## ✨ Features

- **🏠 Home Page** — Hero banner, 8 randomly featured players, and a full teams overview
- **🔍 Player Database** — Searchable and filterable grid of all players
- **🏳️ Teams Browser** — Browse all participating nations with player counts and flag emojis
- **📋 Team Detail** — View the full squad roster for any team
- **⚽ Match Simulator** — Build custom squads (11 starters + 7 subs) and simulate World Cup matches against AI
- **🌙 Dark / Light Theme** — Toggleable theme with persistent preference via `localStorage`
- **⚡ Live Search & Filters** — Client-side instant filtering by name, nationality, and position
- **🎬 Scroll Animations** — Smooth entrance animations powered by `IntersectionObserver`
- **📡 REST API** — JSON endpoints for players and teams

---

## 🛠️ Tech Stack

| Layer        | Technology                         |
| ------------ | ---------------------------------- |
| **Backend**  | Python 3, Flask 3.1                |
| **Templating** | Jinja2                           |
| **Frontend** | HTML5, Vanilla CSS, Vanilla JS     |
| **Data**     | CSV files (no database required)   |
| **Styling**  | Tailwind-inspired utility classes  |

---

## 📂 Project Structure

```
project/
├── main.py                  # Application entry point
├── config.py                # Flask configuration (dev / prod)
├── requirements.txt         # Python dependencies
│
├── app/
│   ├── __init__.py          # Application factory (create_app)
│   ├── data_loader.py       # CSV data loader & Player model
│   └── routes.py            # Page routes & REST API endpoints
│
├── data/
│   └── teams/               # One CSV file per national team
│       ├── argentina.csv
│       ├── brazil.csv
│       ├── england.csv
│       ├── france.csv
│       ├── germany.csv
│       ├── japan.csv
│       ├── mexico.csv
│       ├── netherlands.csv
│       ├── portugal.csv
│       ├── south_korea.csv
│       ├── spain.csv
│       └── usa.csv
│
├── templates/
│   ├── base.html            # Base layout template
│   ├── index.html           # Home page
│   ├── players.html         # Player database page
│   ├── teams.html           # Teams overview page
│   └── team_detail.html     # Single team roster page
│
└── static/
    ├── css/
    │   └── style.css        # Global styles
    ├── js/
    │   └── main.js          # Theme toggle, search, filters, modals
    └── img/
        ├── default.png      # Default player placeholder image
        ├── hero-bg.png      # Hero banner background
        └── players/         # Player headshot images
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+** installed on your system

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/SadmanSakibKhan11/KickoffXI.git
   cd KickoffXI
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**

   - **Windows:**
     ```bash
     .venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Run the development server**

   ```bash
   python main.py
   ```

6. **Open in your browser**

   Navigate to [http://localhost:5000](http://localhost:5000)

---

## 📡 API Reference

All API endpoints return JSON.

### `GET /api/players`

Returns a list of players. Supports the following query parameters:

| Parameter     | Type   | Description                              |
| ------------- | ------ | ---------------------------------------- |
| `q`           | string | Search by name, nationality, or position |
| `nationality` | string | Filter by exact nationality              |
| `position`    | string | Filter by primary position               |
| `secondary`   | string | Filter by secondary position             |

**Example:**

```
GET /api/players?q=messi&nationality=Argentina
```

### `GET /api/players/<id>`

Returns a single player by their integer ID.

**Example:**

```
GET /api/players/1
```

### `GET /api/teams`

Returns all teams with player counts and flag emojis.

---

## 📄 CSV Data Format

Each team CSV file in `data/teams/` follows this schema:

| Column               | Required | Description                                |
| -------------------- | -------- | ------------------------------------------ |
| `name`               | ✅        | Player's full name                         |
| `primary_position`   | ✅        | Main position (Goalkeeper, Defender, etc.)  |
| `secondary_position` | ❌        | Optional secondary position                |
| `nationality`        | ✅        | Country name (must match the file's team)  |
| `image`              | ❌        | Relative path to headshot under `static/img/` |

**Example (`germany.csv`):**

```csv
name,primary_position,secondary_position,nationality,image
Manuel Neuer,Goalkeeper,,Germany,players/manual_neuer.png
Jamal Musiala,Defender,Midfielder,Germany,players/jamal_musiala.png
Florian Wirtz,Midfielder,Defender,Germany,players/default.png
```

### Adding a New Team

1. Create a new CSV file in `data/teams/` (e.g., `italy.csv`)
2. Follow the column format above
3. Optionally add player images to `static/img/players/`
4. Add the country's flag emoji to the `COUNTRY_FLAGS` dict in `app/routes.py`
5. Restart the server — the new team will be loaded automatically

---

## ⚙️ Configuration

The app supports **development** and **production** configurations via `config.py`:

| Setting                | Default                        | Description                           |
| ---------------------- | ------------------------------ | ------------------------------------- |
| `SECRET_KEY`           | `dev-secret-key-...`           | Flask secret key (override via env)   |
| `APP_NAME`             | `KickoffXI`                    | Application display name              |
| `APP_DESCRIPTION`      | `Player Database — Browse...`  | Application description               |
| `DEFAULT_PLAYER_IMAGE` | `players/default.png`          | Fallback image for players            |
| `DEBUG`                | `True` (dev) / `False` (prod)  | Flask debug mode                      |

Set the environment via the `FLASK_CONFIG` environment variable:

```bash
# Production
set FLASK_CONFIG=production    # Windows
export FLASK_CONFIG=production # Linux/macOS

python main.py
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/add-italy-squad`)
3. Commit your changes (`git commit -m "Add Italy squad data"`)
4. Push to the branch (`git push origin feature/add-italy-squad`)
5. Open a Pull Request

---

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">
  Built with ❤️ for the beautiful game
</p>
=======

              KICKOFFXI
      FIFA WORLD CUP 2026 PLAYER DATABASE


Project Status
--------------
Currently Under Development

Description
-----------
KickoffXI is a modern web application built using Flask that allows users
to explore the players participating in the FIFA World Cup 2026.

The goal of this project is to provide a fast, clean, and visually appealing
player database where users can search players, browse national teams,
view player profiles, and build their own Favorite XI.

This project is being developed primarily for learning, portfolio purposes,
and to demonstrate full-stack web development skills.

---------------------------------------------------------

Current Features
----------------
• Modern responsive interface
• FIFA World Cup inspired design
• Live search
• Search by player name
• Search by nationality
• Search by primary position
• Search by secondary position
• Featured players section
• Team selection grid
• Team pages
• Player detail popup
• Dark / Light mode
• Responsive layout
• Smooth transitions

---------------------------------------------------------

Planned Features
----------------
• Complete World Cup 2026 player database
• more than 20+ national teams
• Custom player images
• Favorite XI Builder
• Seven-player bench
• User dashboard
• Advanced player filters
• Improved animations
• Performance optimization

---------------------------------------------------------

Technology Stack
----------------
Backend
• Python
• Flask

Frontend
• HTML5
• Tailwind CSS
• JavaScript

Data Storage
• CSV Files
  (One CSV file for each national team)

Version Control
• Git
• GitHub

---------------------------------------------------------

Project Structure
-----------------

project/

│
├── app/
├── data/
│   └── teams/
│       ├── germany.csv
│       ├── france.csv
│       └── ...
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│       └── players/
│           ├── germany/
│           ├── france/
│           └── ...
│
├── templates/
├── main.py
└── requirements.txt

---------------------------------------------------------

Player Database Format
----------------------

Each team is stored inside its own CSV file.

Example:

germany.csv

Columns

name
nationality
primary_position
secondary_position
image

Example Entry

Jamal Musiala,CAM,LW,Germany,players/germany/jamal_musiala.png

---------------------------------------------------------

How to Add a New Team
---------------------

1. Create a new CSV file.

Example

france.csv

2. Place it inside

data/teams/

3. Create a matching image folder

static/img/players/france/

4. Add player images.

5. Update the image column inside the CSV.

No code changes should be required.


---------------------------------------------------------

Roadmap

[X] Flask project setup
[X] Responsive UI
[X] Homepage
[X] Player database
[X] CSV-based data storage
[X] Live search
[X] Team pages
[ ] Complete Germany squad
[ ] Remaining 47 teams
[ ] Custom player images
[ ] Favorite XI Builder
[ ] User Dashboard
[ ] Player comparison
[ ] Statistics pages
[ ] Final deployment

---------------------------------------------------------

Disclaimer

This project is a fan-made educational project created for learning and
portfolio purposes only.

It is not affiliated with, endorsed by, or sponsored by FIFA.

All trademarks, player names, national team names, and tournament-related
assets belong to their respective owners.

---------------------------------------------------------

Author

Sadman Sakib
B.Sc. in Computer Science & Engineering

Project Name:
KickoffXI – FIFA World Cup 2026 Player Database

=========================================================

