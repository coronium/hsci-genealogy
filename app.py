#!/usr/bin/env python3
"""
Academic Genealogy Explorer - Conference Booth Application
Production version for web deployment
"""

import sqlite3
import csv
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
import unicodedata
import re

app = Flask(__name__)

# Production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'conference-booth-2025-change-in-production')

# Paths - configurable for production
DATA_DIR = os.environ.get('DATA_DIR', 'data')
DISSERTATIONS_CSV = os.path.join(DATA_DIR, 'dissertations.csv')
CORRECTIONS_LOG = os.path.join(DATA_DIR, 'corrections_log.csv')
DB_PATH = os.path.join(DATA_DIR, 'genealogy.db')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def normalize_search_text(text):
    """Remove diacritics and convert to lowercase for search matching."""
    if not text:
        return ""
    # Normalize to NFD (decomposed form) and remove combining characters
    nfd = unicodedata.normalize('NFD', text)
    without_diacritics = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    return without_diacritics.lower().strip()


def init_database():
    """Initialize SQLite database from CSV file."""
    print("Checking database...")
    
    # Only initialize if database doesn't exist OR if explicitly requested
    if os.path.exists(DB_PATH) and not os.environ.get('FORCE_REINIT'):
        print(f"Database already exists at {DB_PATH}. Skipping initialization.")
        print("Set FORCE_REINIT=1 environment variable to force re-initialization.")
        return
    
    print("Initializing database...")
    
    # Remove old database if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE people (
            person_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            years TEXT,
            name_normalized TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE dissertations (
            dissertation_id TEXT PRIMARY KEY,
            author_id TEXT,
            author_name TEXT,
            title TEXT,
            year TEXT,
            school TEXT,
            school_id TEXT,
            department TEXT,
            subject_broad TEXT,
            FOREIGN KEY (author_id) REFERENCES people(person_id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE advisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dissertation_id TEXT,
            advisor_id TEXT,
            advisor_name TEXT,
            advisor_role TEXT,
            advisor_number INTEGER,
            FOREIGN KEY (dissertation_id) REFERENCES dissertations(dissertation_id),
            FOREIGN KEY (advisor_id) REFERENCES people(person_id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE schools (
            school_id TEXT PRIMARY KEY,
            school_name TEXT NOT NULL,
            school_name_normalized TEXT
        )
    ''')
    
    # Create indexes for faster searches
    c.execute('CREATE INDEX idx_people_normalized ON people(name_normalized)')
    c.execute('CREATE INDEX idx_schools_normalized ON schools(school_name_normalized)')
    c.execute('CREATE INDEX idx_advisors_advisor_id ON advisors(advisor_id)')
    c.execute('CREATE INDEX idx_advisors_dissertation_id ON advisors(dissertation_id)')
    
    conn.commit()
    
    # Load data from CSV
    if not os.path.exists(DISSERTATIONS_CSV):
        print(f"Warning: {DISSERTATIONS_CSV} not found. Database created but empty.")
        print(f"Please upload your dissertations.csv file to the {DATA_DIR} directory.")
        conn.close()
        return
    
    print(f"Loading data from {DISSERTATIONS_CSV}...")
    
    people_dict = {}
    schools_dict = {}
    
    # Detect delimiter
    with open(DISSERTATIONS_CSV, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        delimiter = '\t' if first_line.count('\t') > first_line.count(',') else ','
        print(f"Detected delimiter: {'TAB' if delimiter == chr(9) else 'COMMA'}")
    
    with open(DISSERTATIONS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        
        row_count = 0
        for row in reader:
            row_count += 1
            
            # Add author to people
            author_id = row.get('Author_ID', '').strip()
            author_name = row.get('Author_Name', '').strip()
            years = row.get('Years', '').strip()
            
            if author_id and author_name:
                if author_id not in people_dict:
                    people_dict[author_id] = {
                        'person_id': author_id,
                        'name': author_name,
                        'years': years,
                        'name_normalized': normalize_search_text(author_name)
                    }
            
            # Add school
            school_id = row.get('School_ID', '').strip()
            school_name = row.get('School', '').strip()
            
            if school_id and school_name:
                if school_id not in schools_dict:
                    schools_dict[school_id] = {
                        'school_id': school_id,
                        'school_name': school_name,
                        'school_name_normalized': normalize_search_text(school_name)
                    }
            
            # Add advisors to people
            for i in range(1, 9):  # Advisor_1 through Advisor_8
                advisor_id = row.get(f'Advisor_ID_{i}', '').strip()
                advisor_name = row.get(f'Advisor_Name_{i}', '').strip()
                
                if advisor_id and advisor_name and advisor_id != 'na':
                    if advisor_id not in people_dict:
                        people_dict[advisor_id] = {
                            'person_id': advisor_id,
                            'name': advisor_name,
                            'years': '',
                            'name_normalized': normalize_search_text(advisor_name)
                        }
            
            # Insert dissertation
            dissertation_id = row.get('ID', '').strip()
            if dissertation_id:
                c.execute('''
                    INSERT OR IGNORE INTO dissertations 
                    (dissertation_id, author_id, author_name, title, year, school, school_id, department, subject_broad)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    dissertation_id,
                    author_id,
                    author_name,
                    row.get('Title', '').strip(),
                    row.get('Year', '').strip(),
                    school_name,
                    school_id,
                    row.get('Department', '').strip(),
                    row.get('Subject_broad', '').strip()
                ))
                
                # Insert advisor relationships
                for i in range(1, 9):
                    advisor_id = row.get(f'Advisor_ID_{i}', '').strip()
                    advisor_name = row.get(f'Advisor_Name_{i}', '').strip()
                    advisor_role = row.get(f'Advisor_Role_{i}', '').strip()
                    
                    if advisor_id and advisor_id != 'na':
                        c.execute('''
                            INSERT INTO advisors 
                            (dissertation_id, advisor_id, advisor_name, advisor_role, advisor_number)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (dissertation_id, advisor_id, advisor_name, advisor_role, i))
    
    # Insert all people
    for person_data in people_dict.values():
        c.execute('''
            INSERT OR IGNORE INTO people (person_id, name, years, name_normalized)
            VALUES (?, ?, ?, ?)
        ''', (person_data['person_id'], person_data['name'], person_data['years'], person_data['name_normalized']))
    
    # Insert all schools
    for school_data in schools_dict.values():
        c.execute('''
            INSERT OR IGNORE INTO schools (school_id, school_name, school_name_normalized)
            VALUES (?, ?, ?)
        ''', (school_data['school_id'], school_data['school_name'], school_data['school_name_normalized']))
    
    conn.commit()
    
    # Print stats
    c.execute('SELECT COUNT(*) FROM people')
    people_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM dissertations')
    diss_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM schools')
    school_count = c.fetchone()[0]
    
    print(f"Database initialized: {people_count} people, {diss_count} dissertations, {school_count} schools")
    print(f"Processed {row_count} rows from CSV")
    
    conn.close()


def log_correction(user_name, action_type, record_id, details):
    """Log a correction to the CSV file."""
    file_exists = os.path.exists(CORRECTIONS_LOG)
    
    with open(CORRECTIONS_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow(['Timestamp', 'User_Name', 'Action_Type', 'Record_ID', 'Details'])
        
        writer.writerow([
            datetime.now().isoformat(),
            user_name,
            action_type,
            record_id,
            details
        ])


def get_person_affiliations(person_id):
    """Get all university affiliations for a person (as student and/or faculty)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    affiliations = {}
    
    # Where they were a student
    c.execute('''
        SELECT DISTINCT school, school_id, year
        FROM dissertations
        WHERE author_id = ?
    ''', (person_id,))
    
    for school, school_id, year in c.fetchall():
        if school:
            key = school_id if school_id else school
            if key not in affiliations:
                affiliations[key] = {
                    'school': school,
                    'student': True,
                    'faculty': False,
                    'year': year
                }
    
    # Where they were faculty (advised students)
    c.execute('''
        SELECT DISTINCT d.school, d.school_id
        FROM advisors a
        JOIN dissertations d ON a.dissertation_id = d.dissertation_id
        WHERE a.advisor_id = ?
    ''', (person_id,))
    
    for school, school_id in c.fetchall():
        if school:
            key = school_id if school_id else school
            if key not in affiliations:
                affiliations[key] = {
                    'school': school,
                    'student': False,
                    'faculty': True,
                    'year': None
                }
            else:
                affiliations[key]['faculty'] = True
    
    conn.close()
    return list(affiliations.values())


def get_descendants_count(person_id, visited=None):
    """Recursively count all descendants and max generation depth."""
    if visited is None:
        visited = set()
    
    if person_id in visited:
        return 0, 0
    
    visited.add(person_id)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get direct students
    c.execute('''
        SELECT DISTINCT d.author_id
        FROM advisors a
        JOIN dissertations d ON a.dissertation_id = d.dissertation_id
        WHERE a.advisor_id = ?
    ''', (person_id,))
    
    students = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    
    if not students:
        return 0, 0
    
    total_descendants = len(students)
    max_depth = 1
    
    for student_id in students:
        descendant_count, depth = get_descendants_count(student_id, visited)
        total_descendants += descendant_count
        max_depth = max(max_depth, depth + 1)
    
    return total_descendants, max_depth


# Routes

@app.route('/')
def index():
    """Main search page."""
    return render_template('search.html')


@app.route('/health')
def health():
    """Health check endpoint for monitoring."""
    try:
        # Check database connectivity
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM people')
        count = c.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'people_count': count
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/schools')
def get_schools():
    """API endpoint for school autocomplete."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT school_name FROM schools ORDER BY school_name')
    schools = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(schools)


@app.route('/search', methods=['POST'])
def search():
    """Search for people by name or university."""
    name_query = request.form.get('name_search', '').strip()
    school_query = request.form.get('school_search', '').strip()
    
    if not name_query and not school_query:
        return render_template('search.html', error="Please enter a name or university")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    results = []
    
    if name_query:
        # Search by name - split into parts to match "Ronald Numbers" with "Numbers, Ronald"
        name_normalized = normalize_search_text(name_query)
        
        # Split into individual words and filter out empty strings
        name_parts = [part.strip() for part in name_normalized.split() if part.strip()]
        
        if name_parts:
            try:
                # Build query to match all parts (in any order)
                where_clauses = []
                params = []
                for part in name_parts:
                    where_clauses.append('name_normalized LIKE ?')
                    params.append(f'%{part}%')
                
                query = f'''
                    SELECT person_id, name, years
                    FROM people
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY name
                '''
                
                c.execute(query, tuple(params))
                
                for person_id, name, years in c.fetchall():
                    affiliations = get_person_affiliations(person_id)
                    results.append({
                        'person_id': person_id,
                        'name': name,
                        'years': years,
                        'affiliations': affiliations
                    })
            except Exception as e:
                # Log error and fall back to simple search
                print(f"Search error: {e}")
                # Fallback to original simple search
                c.execute('''
                    SELECT person_id, name, years
                    FROM people
                    WHERE name_normalized LIKE ?
                    ORDER BY name
                ''', (f'%{name_normalized}%',))
                
                for person_id, name, years in c.fetchall():
                    affiliations = get_person_affiliations(person_id)
                    results.append({
                        'person_id': person_id,
                        'name': name,
                        'years': years,
                        'affiliations': affiliations
                    })
    
    elif school_query:
        # Search by university - get all people associated with that school
        school_normalized = normalize_search_text(school_query)
        
        # Get school_id
        c.execute('''
            SELECT school_id, school_name
            FROM schools
            WHERE school_name_normalized LIKE ?
            LIMIT 1
        ''', (f'%{school_normalized}%',))
        
        school_row = c.fetchone()
        if not school_row:
            conn.close()
            return render_template('search.html', error="University not found")
        
        school_id, school_name = school_row
        
        # Get all people who studied or taught there
        people_ids = set()
        
        # Students
        c.execute('''
            SELECT DISTINCT author_id
            FROM dissertations
            WHERE school_id = ? OR school = ?
        ''', (school_id, school_name))
        
        for row in c.fetchall():
            if row[0]:
                people_ids.add(row[0])
        
        # Faculty
        c.execute('''
            SELECT DISTINCT a.advisor_id
            FROM advisors a
            JOIN dissertations d ON a.dissertation_id = d.dissertation_id
            WHERE d.school_id = ? OR d.school = ?
        ''', (school_id, school_name))
        
        for row in c.fetchall():
            if row[0]:
                people_ids.add(row[0])
        
        # Get details for all people
        for person_id in people_ids:
            c.execute('SELECT name, years FROM people WHERE person_id = ?', (person_id,))
            person_row = c.fetchone()
            if person_row:
                affiliations = get_person_affiliations(person_id)
                results.append({
                    'person_id': person_id,
                    'name': person_row[0],
                    'years': person_row[1],
                    'affiliations': affiliations
                })
        
        results.sort(key=lambda x: x['name'])
    
    conn.close()
    
    return render_template('search.html', results=results, name_query=name_query, school_query=school_query)


@app.route('/person/<person_id>')
def person_detail(person_id):
    """Show detailed genealogy page for a person."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get person details
    c.execute('SELECT name, years FROM people WHERE person_id = ?', (person_id,))
    person_row = c.fetchone()
    
    if not person_row:
        conn.close()
        return "Person not found", 404
    
    person_name, years = person_row
    
    # Get dissertation details if they have one
    c.execute('''
        SELECT title, year, school, department, subject_broad, dissertation_id
        FROM dissertations
        WHERE author_id = ?
    ''', (person_id,))
    
    diss_row = c.fetchone()
    dissertation = None
    
    if diss_row:
        dissertation = {
            'title': diss_row[0] or 'Unknown',
            'year': diss_row[1] or 'Unknown',
            'school': diss_row[2] or 'Unknown',
            'department': diss_row[3] or 'Unknown',
            'subject': diss_row[4] or 'Unknown',
            'dissertation_id': diss_row[5]
        }
        
        # Get advisors
        c.execute('''
            SELECT advisor_id, advisor_name, advisor_role, advisor_number
            FROM advisors
            WHERE dissertation_id = ?
            ORDER BY advisor_number
        ''', (diss_row[5],))
        
        advisors = []
        for adv_id, adv_name, adv_role, adv_num in c.fetchall():
            advisors.append({
                'advisor_id': adv_id,
                'name': adv_name or 'Unknown',
                'role': adv_role or 'Advisor'
            })
        
        dissertation['advisors'] = advisors
    
    # Get students (people this person advised)
    c.execute('''
        SELECT DISTINCT d.author_id, p.name, d.year, d.school
        FROM advisors a
        JOIN dissertations d ON a.dissertation_id = d.dissertation_id
        JOIN people p ON d.author_id = p.person_id
        WHERE a.advisor_id = ?
        ORDER BY d.year, p.name
    ''', (person_id,))
    
    students = []
    for student_id, student_name, year, school in c.fetchall():
        students.append({
            'student_id': student_id,
            'name': student_name,
            'year': year or 'Unknown',
            'school': school or 'Unknown'
        })
    
    conn.close()
    
    # Calculate genealogy stats
    total_descendants, max_generations = get_descendants_count(person_id)
    direct_students = len(students)
    
    affiliations = get_person_affiliations(person_id)
    
    return render_template('person.html',
                         person_id=person_id,
                         person_name=person_name,
                         years=years or 'Unknown',
                         dissertation=dissertation,
                         students=students,
                         affiliations=affiliations,
                         direct_students=direct_students,
                         total_descendants=total_descendants,
                         max_generations=max_generations)


@app.route('/edit/<person_id>', methods=['GET', 'POST'])
def edit_person(person_id):
    """Edit or add person information."""
    if request.method == 'POST':
        user_name = request.form.get('user_name', '').strip()
        
        if not user_name:
            return "Your name is required", 400
        
        # Collect form data
        details = {
            'person_name': request.form.get('person_name', '').strip(),
            'years': request.form.get('years', '').strip(),
            'school': request.form.get('school', '').strip(),
            'department': request.form.get('department', '').strip(),
            'title': request.form.get('title', '').strip(),
            'year': request.form.get('year', '').strip()
        }
        
        # Log the correction
        log_correction(user_name, 'edit', person_id, str(details))
        
        return redirect(url_for('person_detail', person_id=person_id))
    
    # GET request - show edit form
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get person details
    c.execute('SELECT name, years FROM people WHERE person_id = ?', (person_id,))
    person_row = c.fetchone()
    
    if not person_row:
        conn.close()
        return "Person not found", 404
    
    person_name, years = person_row
    
    # Get dissertation details if they have one
    c.execute('''
        SELECT title, year, school, department, subject_broad
        FROM dissertations
        WHERE author_id = ?
    ''', (person_id,))
    
    diss_row = c.fetchone()
    dissertation = None
    
    if diss_row:
        dissertation = {
            'title': diss_row[0] or '',
            'year': diss_row[1] or '',
            'school': diss_row[2] or '',
            'department': diss_row[3] or '',
            'subject': diss_row[4] or ''
        }
    
    conn.close()
    
    return render_template('edit.html',
                         person_id=person_id,
                         person_name=person_name,
                         years=years or '',
                         dissertation=dissertation)


@app.route('/add', methods=['GET', 'POST'])
def add_person():
    """Add a new person to the database."""
    if request.method == 'POST':
        user_name = request.form.get('user_name', '').strip()
        
        if not user_name:
            return "Your name is required", 400
        
        # Collect form data
        details = {
            'person_name': request.form.get('person_name', '').strip(),
            'years': request.form.get('years', '').strip(),
            'school': request.form.get('school', '').strip(),
            'department': request.form.get('department', '').strip(),
            'title': request.form.get('title', '').strip(),
            'year': request.form.get('year', '').strip()
        }
        
        # Generate a temporary person_id
        import uuid
        new_person_id = f"NEW_{uuid.uuid4().hex[:8]}"
        
        # Log the new person
        log_correction(user_name, 'add_new', new_person_id, str(details))
        
        return render_template('confirmation.html', message=f"Thank you! Your information has been recorded for {details['person_name']}")
    
    # GET request - show add form
    return render_template('add.html')


@app.route('/admin/download-corrections')
def download_corrections():
    """Download the corrections log file. Hidden admin endpoint."""
    from flask import send_file
    
    if not os.path.exists(CORRECTIONS_LOG):
        return "No corrections log found", 404
    
    return send_file(
        CORRECTIONS_LOG,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'corrections_log_{datetime.now().strftime("%Y%m%d")}.csv'
    )


if __name__ == '__main__':
    # Initialize database on startup (only if doesn't exist)
    init_database()
    
    # Get port from environment variable (for deployment) or use 5001 for local
    port = int(os.environ.get('PORT', 5001))
    
    # Run the app
    print("\n" + "="*50)
    print("Academic Genealogy Explorer")
    print("="*50)
    print(f"\nStarting server on port {port}")
    print("Press Ctrl+C to stop\n")
    
    # Use debug mode only if explicitly set
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)