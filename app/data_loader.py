import os
import csv
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)


def sanitize_filename(name):
    """
    Convert a player name to a filesystem-safe filename.

    Rules:
        1. Normalize Unicode (NFD) and strip combining marks (accents).
        2. Convert to lowercase.
        3. Remove apostrophes.
        4. Replace spaces with underscores.
        5. Remove any characters that are not alphanumeric or underscores.
        6. Collapse consecutive underscores into one.
        7. Strip leading/trailing underscores.

    Examples:
        "Jamal Musiala"   → "jamal_musiala"
        "Kylian Mbappé"   → "kylian_mbappe"
        "Antonio Rüdiger" → "antonio_rudiger"
        "O'Brien"         → "obrien"
    """
    # Decompose Unicode characters and strip combining marks (accents)
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))

    # Lowercase
    ascii_name = ascii_name.lower()

    # Remove apostrophes
    ascii_name = ascii_name.replace("'", "").replace("\u2019", "")

    # Replace spaces with underscores
    ascii_name = ascii_name.replace(' ', '_')

    # Remove any character that is not alphanumeric or underscore
    ascii_name = re.sub(r'[^a-z0-9_]', '', ascii_name)

    # Collapse consecutive underscores
    ascii_name = re.sub(r'_+', '_', ascii_name)

    # Strip leading/trailing underscores
    ascii_name = ascii_name.strip('_')

    return ascii_name


class Player:
    """
    Represents a player in memory.
    Image paths are auto-generated from nationality and name.

    Two-layer image system:
        - frame:  teams/<country>/frame.png         (one per country, reusable)
        - player: teams/<country>/players/<name>.png (one per player, transparent BG)
    """
    def __init__(self, id, name, primary_position, secondary_position, nationality):
        self.id = id
        self.name = name
        self.primary_position = primary_position
        self.secondary_position = secondary_position if secondary_position else None
        self.nationality = nationality

    @property
    def player_image_path(self):
        """
        Relative image path for this player's transparent PNG.

        Format: teams/<country>/players/<sanitized_name>.png

        Example:
            Nationality: Germany, Name: Jamal Musiala
            → teams/germany/players/jamal_musiala.png
        """
        country_folder = sanitize_filename(self.nationality)
        player_file = sanitize_filename(self.name) + '.png'
        return f'teams/{country_folder}/players/{player_file}'

    @property
    def frame_image_path(self):
        """
        Relative image path for this player's country frame.

        Format: teams/<country>/frame.png

        Example:
            Nationality: Germany → teams/germany/frame.png
        """
        country_folder = sanitize_filename(self.nationality)
        return f'teams/{country_folder}/frame.png'

    def _resolve_image_url(self, rel_path, fallback_config_key):
        """
        Resolve a relative image path to a full static URL.
        Falls back to the configured default if the file does not exist.
        """
        from flask import url_for, current_app

        fallback = current_app.config.get(fallback_config_key, rel_path)
        static_folder = current_app.static_folder

        if not static_folder:
            return url_for('static', filename='img/' + fallback)

        if not os.path.isabs(static_folder):
            static_folder = os.path.abspath(os.path.join(current_app.root_path, static_folder))

        img_base_dir = os.path.normpath(os.path.join(static_folder, 'img'))

        # Check if the auto-generated image file exists
        target_path = os.path.normpath(os.path.join(img_base_dir, rel_path))
        if os.path.isfile(target_path):
            return url_for('static', filename='img/' + rel_path)

        # Fallback to default image
        return url_for('static', filename='img/' + fallback)

    @property
    def player_image_url(self):
        """Full static URL for this player's transparent PNG (with fallback)."""
        return self._resolve_image_url(self.player_image_path, 'DEFAULT_PLAYER_IMAGE')

    @property
    def frame_image_url(self):
        """Full static URL for this player's country frame (with fallback)."""
        return self._resolve_image_url(self.frame_image_path, 'DEFAULT_FRAME_IMAGE')

    def to_dict(self):
        """Serialize player to a dictionary (for JSON API responses)."""
        return {
            'id': self.id,
            'name': self.name,
            'nationality': self.nationality,
            'primary_position': self.primary_position,
            'secondary_position': self.secondary_position,
            'player_image_url': self.player_image_url,
            'frame_image_url': self.frame_image_url,
        }

    def __repr__(self):
        return f'<Player {self.name} ({self.nationality})>'


class CSVDataLoader:
    """
    CSV loader that dynamically scans data/teams/ and loads player records.
    Loads once during startup and processes requests from memory.
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.players = []
        self.players_by_id = {}
        self.nationalities = []
        self.load_data()

    def load_data(self):
        players_list = []
        next_id = 1
        
        teams_dir = os.path.join(self.data_dir, 'teams')
        if not os.path.exists(teams_dir):
            logger.error(f"[ERROR] Directory {teams_dir} does not exist. Cannot load player data.")
            return

        # Sort files to ensure deterministic ID assignment
        try:
            files = sorted(os.listdir(teams_dir))
        except Exception as e:
            logger.error(f"[ERROR] Failed to list contents of {teams_dir}: {e}")
            return

        for filename in files:
            if not filename.lower().endswith('.csv'):
                continue
            
            filepath = os.path.join(teams_dir, filename)
            
            # Skip empty files safely
            try:
                if os.path.getsize(filepath) == 0:
                    logger.warning(f"[WARNING] Skipping empty CSV file: {filename}")
                    continue
            except Exception as e:
                logger.warning(f"[WARNING] Could not check size of {filename}: {e}")
                continue

            try:
                with open(filepath, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    # Validate headers — image column is no longer required
                    required_headers = {'name', 'primary_position', 'secondary_position', 'nationality'}
                    if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
                        logger.warning(f"[WARNING] Skipping malformed CSV (missing required headers): {filename}")
                        continue
                    
                    for row_idx, row in enumerate(reader, start=2):
                        # Handle malformed rows or missing columns gracefully
                        try:
                            name = row.get('name')
                            primary_pos = row.get('primary_position')
                            secondary_pos = row.get('secondary_position')
                            nationality = row.get('nationality')
                            
                            # Validation: name, primary_position, nationality must be present
                            if not name or not primary_pos or not nationality:
                                logger.warning(f"[WARNING] Skipping malformed row {row_idx} in {filename}: missing key data.")
                                continue
                            
                            player = Player(
                                id=next_id,
                                name=name.strip(),
                                primary_position=primary_pos.strip(),
                                secondary_position=secondary_pos.strip() if secondary_pos else None,
                                nationality=nationality.strip(),
                            )
                            players_list.append(player)
                            next_id += 1
                        except Exception as row_err:
                            logger.warning(f"[WARNING] Error parsing row {row_idx} in {filename}: {row_err}")
                            continue
            except Exception as file_err:
                logger.error(f"[ERROR] Failed to read CSV file {filename}: {file_err}")
                continue
        
        self.players = players_list
        self.players_by_id = {p.id: p for p in self.players}
        self.nationalities = sorted(list(set(p.nationality for p in self.players)))
        logger.info(f"[OK] Successfully loaded {len(self.players)} players from CSV files across {len(self.nationalities)} teams.")

    def get_all_players(self):
        """Returns all players sorted by name."""
        return sorted(self.players, key=lambda p: p.name.lower())

    def get_player_by_id(self, player_id):
        """Find a player by their integer ID."""
        return self.players_by_id.get(player_id)

    def get_players_by_nationality(self, nationality):
        """Returns all players of a specific nationality sorted by name."""
        filtered = [p for p in self.players if p.nationality.lower() == nationality.lower()]
        return sorted(filtered, key=lambda p: p.name.lower())

    def get_teams(self, flags_mapping):
        """
        Dynamically calculate teams overview list of dicts.
        Sorted by nationality name.
        """
        counts = {}
        for p in self.players:
            counts[p.nationality] = counts.get(p.nationality, 0) + 1
        
        teams_data = []
        for nationality in sorted(counts.keys()):
            teams_data.append({
                'nationality': nationality,
                'count': counts[nationality],
                'flag': flags_mapping.get(nationality, '🏳️')
            })
        return teams_data
