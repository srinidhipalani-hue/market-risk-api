# Market Risk API

A FastAPI service that downloads stock prices and computes portfolio risk.

## Run locally

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs