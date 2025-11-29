"""
Integration test for hhfloppy event pushing.

This test executes the hhfloppy/test_events.py script, authorizes the push,
and verifies that the test event is correctly stored in the database.
"""
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from rhinventory.extensions import db
from rhinventory.models.events import DBEvent


@pytest.fixture
def flask_server(app):
    """Start a Flask test server and return its URL."""
    # Find an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    
    server = make_server('127.0.0.1', port, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    # Give the server a moment to start
    time.sleep(0.5)
    
    yield f"http://127.0.0.1:{port}/"
    
    # Shutdown server
    server.shutdown()


def test_hhfloppy_test_events_integration(app, flask_server):
    """
    Test the full hhfloppy event pushing flow.
    
    This test:
    1. Starts the Flask server
    2. Runs hhfloppy/test_events.py as a subprocess
    3. Parses the authorization URL from the script output
    4. Authorizes the push key
    5. Waits for the script to complete
    6. Verifies the TestEvent was added to the database
    """
    # Get the path to the hhfloppy test_events.py script
    import hhfloppy
    hhfloppy_path = hhfloppy.__path__[0]
    test_events_script = f"{hhfloppy_path}/test_events.py"
    
    # Generate a unique test data string to identify this test's event
    test_data = f"integration_test_{uuid.uuid7().hex}"
    
    env = os.environ.copy()
    env["EVENT_STORE_ADDRESS"] = flask_server
    
    process = subprocess.Popen(
        [sys.executable, "-u", test_events_script, f"--test-data={test_data}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    
    authorize_url = None
    output_lines = []
    
    url_pattern = re.compile(r'(http://[^\s]+/event_store/authorize[^\s]+)')
    
    start_time = time.time()
    timeout = 30
    
    while time.time() - start_time < timeout:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                break
            time.sleep(0.1)
            continue
            
        output_lines.append(line)
        print(f"[hhfloppy] {line.rstrip()}")
        
        match = url_pattern.search(line)
        if match:
            authorize_url = match.group(1)
            break
    
    assert authorize_url is not None, f"Could not find authorization URL in output:\n{''.join(output_lines)}"
    print(f"Found authorization URL: {authorize_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(authorize_url)
        page.click("#authorize-button")
        page.wait_for_load_state("networkidle")
        browser.close()
    print("Push key authorized via browser")
    
    # Wait for process to finish
    remaining_timeout = timeout - (time.time() - start_time)
    try:
        return_code = process.wait(timeout=max(1, remaining_timeout))
    except subprocess.TimeoutExpired:
        process.kill()
        pytest.fail("Process did not complete within timeout")
    
    assert return_code == 0, f"Process exited with code {return_code}"
    
    # Verify the TestEvent was added to the database
    with app.app_context():
        # Find the event in the database by our unique test data
        test_event = db.session.query(DBEvent).filter(
            DBEvent.namespace == "hhfloppy",
            DBEvent.class_name == "TestEvent",
            DBEvent.data["test_data"].astext == test_data
        ).first()
        
        assert test_event is not None, f"TestEvent with test_data='{test_data}' not found in database"
        
        # Verify event session was created correctly
        event_session = test_event.event_session
        assert event_session is not None
        assert event_session.namespace == "hhfloppy"
        
        print(f"Successfully verified TestEvent in database: {test_event.id}")
