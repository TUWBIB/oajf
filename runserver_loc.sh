export FLASK_APP=app
export FLASK_DEBUG=true
export FLASK_RUN_EXTRA_FILES="./translations/en/LC_MESSAGES/messages.mo"
flask run --host=0.0.0.0 --port 5001
