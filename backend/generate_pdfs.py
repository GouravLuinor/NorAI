from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
TYPES = ['study_notes', 'revision', 'assessment']
OUTPUT_DIR = Path('outputs')

def generate_pdfs():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for doc_type in TYPES:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})

            # Capture all console messages (errors, warnings, logs)
            page.on('console', lambda msg: print(f'[CONSOLE {msg.type}] {msg.text}'))
            page.on('pageerror', lambda err: print(f'[PAGE ERROR] {err}'))

            print(f'\n--- Loading {doc_type} ---')
            page.goto(
                f'http://localhost:5173/print?type={doc_type}',
                wait_until='networkidle'          # ← waits for all network activity to settle
            )
            # Safety net: still wait for the first chapter to appear
            page.wait_for_selector('.print-chapter', timeout=30000)
            page.pdf(
                path=str(OUTPUT_DIR / f'{doc_type}.pdf'),
                print_background=True,
                format='A4',
            )
            page.close()
        browser.close()



if __name__ == '__main__':
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # If a specific type was passed via command line, only generate that one
    if len(sys.argv) > 1 and sys.argv[1] in TYPES:
        TYPES = [sys.argv[1]]
    generate_pdfs()