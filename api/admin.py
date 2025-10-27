"""
Admin API endpoints for managing records.
This file imports the unified FastAPI app from main.py for Vercel deployment.
"""
import sys
import os

# Add parent directory to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Vercel will use this app instance
# All routes are defined in main.py
