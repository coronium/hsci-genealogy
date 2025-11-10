# IsisCB Academic Genealogy Explorer

A Flask web application for exploring academic genealogy relationships in the History of Science field

## Features

- **Search by Name**: Find scholars by their name
- **Search by University**: See all scholars associated with a specific institution
- **Academic Lineage**: View advisor-student relationships and genealogy trees
- **Descendant Statistics**: See total descendants and generation depth
- **User Contributions**: Allow visitors to add missing information or corrections
- **Unicode Support**: Handle international names and diacritics

## Project Structure

```
.
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── render.yaml                # Render.com deployment config
├── Procfile                   # Alternative deployment config
├── templates/                 # HTML templates
│   ├── search.html           # Main search page
│   ├── person.html           # Person detail page
│   ├── edit.html             # Edit form
│   ├── add.html              # Add new person form
│   └── confirmation.html     # Thank you page
├── static/                    # CSS and static files
│   └── style.css             # Stylesheet
└── data/                      # Data directory (on persistent storage)
    ├── dissertations.csv     # Main data file (upload manually)
    ├── genealogy.db          # SQLite database (auto-generated)
    └── corrections_log.csv   # User submissions log
```

## Data Management

### CSV File Format

Your `dissertations.csv` should be with these columns:

- `ID`: Unique dissertation ID
- `Author_ID`: Unique author identifier
- `Author_Name`: Full name
- `Years`: Life years (e.g., "1900-1975")
- `Title`: Dissertation title
- `Year`: Completion year
- `School`: University name
- `School_ID`: Unique school identifier
- `Department`: Department name
- `Subject_broad`: Subject area
- `Advisor_ID_1` through `Advisor_ID_8`: Advisor identifiers
- `Advisor_Name_1` through `Advisor_Name_8`: Advisor names
- `Advisor_Role_1` through `Advisor_Role_8`: Roles (Advisor, Committee Member, etc.)

### Re-uploading Data

To update your dataset:

1. Upload new `dissertations.csv` to the data directory
2. Set environment variable `FORCE_REINIT=1`
3. Restart the service
4. Remove `FORCE_REINIT` variable

### Downloading Corrections

User submissions are logged to `data/corrections_log.csv`. To download:

1. Use Render's Shell to access the file
2. Use `cat /opt/render/project/src/data/corrections_log.csv` to view
3. Copy and save locally for review

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key (auto-generated in production)
- `DATA_DIR`: Path to data directory (default: `data`)
- `PORT`: Server port (auto-set by Render)
- `FLASK_ENV`: Set to `development` for debug mode
- `FORCE_REINIT`: Set to `1` to force database re-initialization

## Technical Details

### Database

- SQLite database auto-generated from CSV on first run
- Optimized with indexes for fast searches
- Normalized search (diacritics removed for matching)
- Recursive queries for descendant counting

