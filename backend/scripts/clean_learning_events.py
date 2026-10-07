"""Rebuild derived quality flags without changing or deleting raw events."""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from app.classroom import clean_events, init_classroom

if __name__ == '__main__':
    init_classroom()
    print(f'Processed {clean_events()} records; raw events preserved.')
