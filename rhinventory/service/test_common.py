

def test_db_running(db_session):
    """Test whether testing DB is running."""
    assert db_session.execute('SELECT 1')
