#!/usr/bin/env python3
"""Run Nextup directly, without a WSGI server. Handy for local work."""
from app import config, create_app

if __name__ == "__main__":
    create_app().run(host=config.HOST, port=config.PORT, debug=False)
