from youinsight import create_app, db

app = create_app()
with app.app_context():
    db.session.commit()
    print('Database session reset')
