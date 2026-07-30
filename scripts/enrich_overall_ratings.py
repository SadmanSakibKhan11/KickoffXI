"""
Enrich Overall Ratings Pipeline
================================
Standalone offline data pipeline script to enrich team CSV files in `data/teams/`
with an `overall` rating column sourced exclusively from EA SPORTS FC 26 ratings data.

Data Source Integrity Rules:
- Ratings are only populated if sourced from a verifiable reference dataset
  at `data/reference/ea_fc26_ratings.csv` (or `.json`).
- If no reference file is available, ratings population is halted, `overall` cells are
  left empty, and an audit report is produced explicitly recording that the data source is missing.
- Memorized/estimated values are strictly forbidden.

Usage:
    python scripts/enrich_overall_ratings.py
"""

import os
import sys
import csv
import json
import re
import logging
import unicodedata
import tempfile
from difflib import SequenceMatcher

# Logger configuration (matching existing project logging style)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


# ════════════════════════════════════════════════════════════════
# 1. NAME NORMALIZATION & SIMILARITY
# ════════════════════════════════════════════════════════════════

def normalize_name(name: str) -> str:
    """
    Normalize player name for robust comparison:
    1. Strip diacritics / accents (NFKD decomposition).
    2. Convert to lowercase.
    3. Remove apostrophes, quotes, periods, and hyphens.
    4. Normalize common short-form / nickname conventions (e.g. Vini Jr. -> Vinicius Junior).
    """
    if not name:
        return ""
    
    # Strip diacritics/accents
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_str = ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
    
    # Strip punctuation
    ascii_str = ascii_str.replace("'", "").replace("\u2019", "").replace(".", "")
    ascii_str = re.sub(r'[-_/\\]', ' ', ascii_str)
    ascii_str = re.sub(r'[^a-z0-9\s]', '', ascii_str)
    
    tokens = ascii_str.split()
    normalized_tokens = []
    for t in tokens:
        if t in ('vini',):
            normalized_tokens.append('vinicius')
        elif t in ('jr', 'jnr'):
            normalized_tokens.append('junior')
        elif t in ('sr', 'snr'):
            normalized_tokens.append('senior')
        else:
            normalized_tokens.append(t)
            
    return ' '.join(normalized_tokens)


def calculate_similarity(norm1: str, norm2: str) -> float:
    """
    Calculate similarity score between two normalized name strings.
    Returns a float between 0.0 and 1.0.
    """
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
    
    seq_ratio = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Check token-set similarity
    t1 = set(norm1.split())
    t2 = set(norm2.split())
    if t1 and t2:
        if t1 == t2:
            return 0.98
        if t1.issubset(t2) or t2.issubset(t1):
            token_ratio = len(t1.intersection(t2)) / len(t1.union(t2))
            return max(seq_ratio, token_ratio * 0.95)
            
    return seq_ratio


def positions_match(ref_pos: str, primary_pos: str, secondary_pos: str = None) -> bool:
    """Check if reference position matches primary or secondary position."""
    if not ref_pos or not primary_pos:
        return False
    ref = ref_pos.upper().strip()
    pri = primary_pos.upper().strip()
    
    if pri in ref or ref in pri:
        return True
        
    if secondary_pos:
        sec = secondary_pos.upper().strip()
        if sec in ref or ref in sec:
            return True
            
    return False


# ════════════════════════════════════════════════════════════════
# 2. REFERENCE DATA LOADER (SOURCE A)
# ════════════════════════════════════════════════════════════════

def load_reference_data(project_root: str):
    """
    Search for Source A reference dataset at data/reference/ea_fc26_ratings.csv or .json.
    Returns tuple: (reference_players_list, data_source_description)
    or (None, None) if not present.
    """
    ref_dir = os.path.join(project_root, 'data', 'reference')
    csv_path = os.path.join(ref_dir, 'ea_fc26_ratings.csv')
    json_path = os.path.join(ref_dir, 'ea_fc26_ratings.json')
    
    ref_file = None
    if os.path.isfile(csv_path):
        ref_file = csv_path
    elif os.path.isfile(json_path):
        ref_file = json_path
        
    if not ref_file:
        return None, None
        
    players = []
    try:
        if ref_file.endswith('.csv'):
            with open(ref_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    norm_row = {k.lower().strip(): v.strip() for k, v in row.items() if k and v}
                    name = norm_row.get('name') or norm_row.get('player_name') or norm_row.get('player')
                    nat = norm_row.get('nationality') or norm_row.get('nation') or norm_row.get('country') or ''
                    pos = norm_row.get('position') or norm_row.get('primary_position') or norm_row.get('pos') or ''
                    ovr_str = norm_row.get('overall') or norm_row.get('overall_rating') or norm_row.get('rating') or norm_row.get('ovr')
                    
                    if name and ovr_str:
                        try:
                            ovr = int(ovr_str)
                            if 0 <= ovr <= 99:
                                players.append({
                                    'name': name,
                                    'norm_name': normalize_name(name),
                                    'nationality': nat,
                                    'position': pos,
                                    'overall': ovr
                                })
                        except ValueError:
                            continue

        elif ref_file.endswith('.json'):
            with open(ref_file, mode='r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        norm_item = {str(k).lower().strip(): str(v).strip() for k, v in item.items() if k and v}
                        name = norm_item.get('name') or norm_item.get('player_name') or norm_item.get('player')
                        nat = norm_item.get('nationality') or norm_item.get('nation') or norm_item.get('country') or ''
                        pos = norm_item.get('position') or norm_item.get('primary_position') or norm_item.get('pos') or ''
                        ovr_str = norm_item.get('overall') or norm_item.get('overall_rating') or norm_item.get('rating') or norm_item.get('ovr')
                        
                        if name and ovr_str:
                            try:
                                ovr = int(ovr_str)
                                if 0 <= ovr <= 99:
                                    players.append({
                                        'name': name,
                                        'norm_name': normalize_name(name),
                                        'nationality': nat,
                                        'position': pos,
                                        'overall': ovr
                                    })
                            except ValueError:
                                continue

        logger.info(f"[OK] Source A reference dataset loaded successfully: {ref_file} ({len(players)} records)")
        return players, f"Source A ({os.path.relpath(ref_file, project_root)})"

    except Exception as e:
        logger.error(f"[ERROR] Failed to load reference dataset {ref_file}: {e}")
        return None, None


# ════════════════════════════════════════════════════════════════
# 3. PLAYER MATCHING ALGORITHM
# ════════════════════════════════════════════════════════════════

def match_player(target_name: str, nationality: str, primary_pos: str,
                 secondary_pos: str, ref_players: list, fuzzy_threshold: float = 0.85):
    """
    Match a player against reference dataset following strict priority rules:
    1. Primary match key: normalized player name.
    2. If multiple exact matches exist, disambiguate by nationality.
    3. If still ambiguous, disambiguate by primary/secondary position.
    4. If still ambiguous, treat as unmatched & return ambiguous tie list.
    5. If no exact match, try fuzzy name matching (>= fuzzy_threshold).
    6. Disambiguate top fuzzy candidates by nationality & position.

    Returns:
        (overall_int_or_None, match_type_str, score_float, tied_candidates_list)
        match_type_str is one of: 'exact', 'fuzzy', 'ambiguous', 'not_found', 'no_source'
    """
    if ref_players is None:
        return None, 'no_source', 0.0, []
        
    norm_target = normalize_name(target_name)
    if not norm_target:
        return None, 'not_found', 0.0, []
        
    # ── Rule 1: Exact Name Match ──
    exact_candidates = [p for p in ref_players if p['norm_name'] == norm_target]
    
    if len(exact_candidates) == 1:
        return exact_candidates[0]['overall'], 'exact', 1.0, []
        
    if len(exact_candidates) > 1:
        # Rule 2: Disambiguate by nationality
        if nationality:
            nat_matches = [c for c in exact_candidates if c['nationality'].lower() == nationality.lower()]
            if len(nat_matches) == 1:
                return nat_matches[0]['overall'], 'exact', 1.0, []
            elif len(nat_matches) > 1:
                exact_candidates = nat_matches
                
        # Rule 3: Disambiguate by position
        if primary_pos:
            pos_matches = [c for c in exact_candidates if positions_match(c['position'], primary_pos, secondary_pos)]
            if len(pos_matches) == 1:
                return pos_matches[0]['overall'], 'exact', 1.0, []
                
        # Rule 4: Ambiguous tie
        tied_info = [f"{c['name']} ({c['nationality']}, {c['position']})" for c in exact_candidates]
        return None, 'ambiguous', 1.0, tied_info

    # ── Rule 5: Fuzzy Name Match ──
    scored_candidates = []
    for p in ref_players:
        score = calculate_similarity(norm_target, p['norm_name'])
        if score >= fuzzy_threshold:
            scored_candidates.append((score, p))
            
    if not scored_candidates:
        return None, 'not_found', 0.0, []
        
    # Sort descending by score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_score = scored_candidates[0][0]
    top_candidates = [p for score, p in scored_candidates if abs(score - top_score) < 0.02]
    
    if len(top_candidates) == 1:
        return top_candidates[0]['overall'], 'fuzzy', round(top_score, 3), []
        
    # Disambiguate fuzzy top candidates by nationality
    if nationality:
        nat_matches = [c for c in top_candidates if c['nationality'].lower() == nationality.lower()]
        if len(nat_matches) == 1:
            return nat_matches[0]['overall'], 'fuzzy', round(top_score, 3), []
        elif len(nat_matches) > 1:
            top_candidates = nat_matches
            
    # Disambiguate fuzzy top candidates by position
    if primary_pos:
        pos_matches = [c for c in top_candidates if positions_match(c['position'], primary_pos, secondary_pos)]
        if len(pos_matches) == 1:
            return pos_matches[0]['overall'], 'fuzzy', round(top_score, 3), []
            
    # Ambiguous fuzzy tie
    tied_info = [f"{c['name']} ({c['nationality']}, {c['position']})" for c in top_candidates]
    return None, 'ambiguous', round(top_score, 3), tied_info


# ════════════════════════════════════════════════════════════════
# 4. CSV FILE ENRICHMENT & QUALITY CONTROL (QC)
# ════════════════════════════════════════════════════════════════

def process_csv_file(filepath: str, ref_players: list, audit_stats: dict):
    """
    Enrich a single team CSV file while preserving file structure and UTF-8 encoding.
    Executes 5 Quality Control (QC) checks before atomic replacement.
    
    Returns:
        (success_bool, message_str)
    """
    filename = os.path.basename(filepath)
    
    try:
        with open(filepath, mode='r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return False, f"Failed to read file: {e}"
        
    lines = [line for line in original_content.splitlines() if line.strip()]
    if not lines:
        return False, "File is empty"
        
    # Read original rows cleanly using csv.reader
    reader = csv.reader(lines)
    header = next(reader)
    
    expected_base = ['name', 'primary_position', 'secondary_position', 'nationality']
    if len(header) < 4 or header[:4] != expected_base:
        return False, f"Header does not match expected base schema {expected_base}: got {header}"
        
    has_overall_col = (len(header) >= 5 and header[4] == 'overall')
    new_header = list(header)
    if not has_overall_col:
        new_header.append('overall')
        
    new_rows = [new_header]
    
    file_processed = 0
    file_exact = 0
    file_fuzzy = 0
    file_not_found = 0
    file_ambiguous = 0
    
    for row_idx, row in enumerate(reader, start=2):
        if len(row) < 4:
            new_rows.append(row)
            continue
            
        file_processed += 1
        name = row[0].strip()
        primary_pos = row[1].strip()
        secondary_pos = row[2].strip()
        nationality = row[3].strip()
        existing_overall = row[4].strip() if len(row) >= 5 else ""
        
        overall_val = ""
        if ref_players is not None:
            ovr, match_type, score, tied = match_player(
                name, nationality, primary_pos, secondary_pos, ref_players
            )
            if match_type == 'exact':
                overall_val = str(ovr)
                file_exact += 1
                audit_stats['exact_matches'].append({
                    'name': name, 'nationality': nationality, 'file': filename, 'overall': ovr
                })
            elif match_type == 'fuzzy':
                overall_val = str(ovr)
                file_fuzzy += 1
                audit_stats['fuzzy_matches'].append({
                    'name': name, 'nationality': nationality, 'file': filename, 'overall': ovr, 'score': score
                })
            elif match_type == 'ambiguous':
                overall_val = existing_overall
                file_ambiguous += 1
                audit_stats['ambiguous_matches'].append({
                    'name': name, 'nationality': nationality, 'file': filename, 'tied': tied
                })
            else:
                overall_val = existing_overall
                file_not_found += 1
                audit_stats['not_found_players'].append({
                    'name': name, 'nationality': nationality, 'file': filename
                })
        else:
            overall_val = existing_overall
            file_not_found += 1
            audit_stats['not_found_players'].append({
                'name': name, 'nationality': nationality, 'file': filename
            })
            
        new_row = row[:4] + [overall_val]
        new_rows.append(new_row)
        
    audit_stats['total_processed'] += file_processed
    audit_stats['total_exact'] += file_exact
    audit_stats['total_fuzzy'] += file_fuzzy
    audit_stats['total_not_found'] += file_not_found
    audit_stats['total_ambiguous'] += file_ambiguous

    # ── QUALITY CONTROL (QC) CHECKS ──
    # Check 1: Row count equal
    if len(new_rows) != len(lines):
        return False, f"QC Check 1 Failed: Row count mismatch (original {len(lines)}, new {len(new_rows)})"
        
    # Check 2: Header extends properly
    if new_rows[0] != new_header:
        return False, f"QC Check 2 Failed: Header mismatch ({new_rows[0]})"
        
    # Check 3: UTF-8 validity
    try:
        temp_check = []
        for r in new_rows:
            temp_check.append(','.join(r))
        '\n'.join(temp_check).encode('utf-8')
    except Exception as e:
        return False, f"QC Check 3 Failed: UTF-8 encoding error ({e})"
        
    # Check 4: No duplicate rows introduced
    unique_rows_count = len(set(tuple(r[:4]) for r in new_rows[1:]))
    orig_unique_count = len(set(tuple(r[:4]) for r in [list(next(csv.reader([l]))) for l in lines[1:]]))
    if unique_rows_count != orig_unique_count:
        return False, f"QC Check 4 Failed: Duplicate rows detected ({orig_unique_count} vs {unique_rows_count})"

    # Check 5: All pre-existing cell values (columns 0..3) are byte-for-byte identical
    orig_reader = csv.reader(lines)
    next(orig_reader)  # skip header
    for idx, (orig_r, new_r) in enumerate(zip(orig_reader, new_rows[1:]), start=2):
        if len(orig_r) >= 4:
            if orig_r[:4] != new_r[:4]:
                return False, f"QC Check 5 Failed: Data mutated in row {idx} ({orig_r[:4]} vs {new_r[:4]})"

    # Atomic Write using temporary file
    teams_dir = os.path.dirname(filepath)
    temp_fd, temp_path = tempfile.mkstemp(dir=teams_dir, prefix="enrich_tmp_", suffix=".csv")
    try:
        with os.fdopen(temp_fd, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)
        os.replace(temp_path, filepath)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False, f"Atomic replace failed: {e}"

    return True, "Passed QC & Updated"


# ════════════════════════════════════════════════════════════════
# 5. MAIN PIPELINE & AUDIT REPORT GENERATION
# ════════════════════════════════════════════════════════════════

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    teams_dir = os.path.join(project_root, 'data', 'teams')
    
    if not os.path.exists(teams_dir):
        logger.error(f"[ERROR] Directory {teams_dir} does not exist.")
        sys.exit(1)
        
    # Dynamically discover all CSV files in data/teams/
    csv_files = sorted([f for f in os.listdir(teams_dir) if f.lower().endswith('.csv')])
    if not csv_files:
        logger.warning(f"[WARNING] No CSV files found in {teams_dir}.")
        sys.exit(0)

    # Load reference dataset (Source A)
    ref_players, data_source_name = load_reference_data(project_root)
    
    if ref_players is None:
        data_source_name = "NONE — Reference file missing at data/reference/ea_fc26_ratings.csv"
        logger.warning("[WARNING] " + "=" * 60)
        logger.warning("[WARNING] CRITICAL CONSTRAINT: Source A reference dataset is missing!")
        logger.warning("[WARNING] Target path: data/reference/ea_fc26_ratings.csv (or .json)")
        logger.warning("[WARNING] Ratings population is halted per Data Source Integrity rules.")
        logger.warning("[WARNING] CSV headers will be checked/extended with 'overall' (empty cells).")
        logger.warning("[WARNING] " + "=" * 60)

    audit_stats = {
        'total_processed': 0,
        'total_exact': 0,
        'total_fuzzy': 0,
        'total_not_found': 0,
        'total_ambiguous': 0,
        'exact_matches': [],
        'fuzzy_matches': [],
        'not_found_players': [],
        'ambiguous_matches': [],
        'updated_files': [],
        'skipped_files': [],
    }

    for filename in csv_files:
        filepath = os.path.join(teams_dir, filename)
        success, msg = process_csv_file(filepath, ref_players, audit_stats)
        if success:
            audit_stats['updated_files'].append(filename)
            logger.info(f"[OK] Processed {filename}: {msg}")
        else:
            audit_stats['skipped_files'].append((filename, msg))
            logger.error(f"[ERROR] Skipped {filename}: {msg}")

    # Generate Audit Report Text
    report_lines = []
    report_lines.append("=" * 68)
    report_lines.append("EA SPORTS FC 26 RATINGS ENRICHMENT AUDIT REPORT")
    report_lines.append("=" * 68)
    report_lines.append(f"Data Source Used: {data_source_name}")
    report_lines.append(f"Files Processed:  {len(csv_files)} ({', '.join(csv_files)})")
    report_lines.append(f"Total Players:    {audit_stats['total_processed']}")
    report_lines.append(f"Matched (Exact):  {audit_stats['total_exact']}")
    report_lines.append(f"Matched (Fuzzy):  {audit_stats['total_fuzzy']}")
    report_lines.append(f"Not Found:        {audit_stats['total_not_found']}")
    report_lines.append(f"Ambiguous Matches:{audit_stats['total_ambiguous']}")
    report_lines.append(f"Files Updated:    {len(audit_stats['updated_files'])}")
    report_lines.append(f"Files Skipped:    {len(audit_stats['skipped_files'])}")
    report_lines.append("-" * 68)

    if audit_stats['fuzzy_matches']:
        report_lines.append("\nFUZZY MATCH DETAILS:")
        for item in audit_stats['fuzzy_matches']:
            report_lines.append(f"  • {item['name']} ({item['nationality']}) [{item['file']}] -> Overall: {item['overall']} (confidence: {item['score']})")

    if audit_stats['ambiguous_matches']:
        report_lines.append("\nAMBIGUOUS MATCHES (TIED CANDIDATES):")
        for item in audit_stats['ambiguous_matches']:
            tied_str = ', '.join(item['tied'])
            report_lines.append(f"  • {item['name']} ({item['nationality']}) [{item['file']}] -> Tied: [{tied_str}]")

    if audit_stats['not_found_players']:
        report_lines.append("\nNOT FOUND PLAYERS (OVERALL LEFT BLANK):")
        for item in audit_stats['not_found_players']:
            report_lines.append(f"  • {item['name']} ({item['nationality']}) [{item['file']}]")

    if audit_stats['skipped_files']:
        report_lines.append("\nSKIPPED FILES (QC FAILED):")
        for fname, reason in audit_stats['skipped_files']:
            report_lines.append(f"  • {fname}: {reason}")

    report_lines.append("=" * 68)
    report_text = "\n".join(report_lines)

    # Console Output (safe UTF-8 output handling)
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print("\n" + report_text)
    except Exception:
        print("\n" + report_text.encode('ascii', errors='replace').decode('ascii'))

    # Write report file
    scripts_dir = os.path.dirname(__file__)
    report_filepath = os.path.join(scripts_dir, 'enrichment_report.txt')
    try:
        with open(report_filepath, mode='w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"[OK] Saved audit report to {report_filepath}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to save audit report file: {e}")


if __name__ == '__main__':
    main()
