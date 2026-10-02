# PocketSmart AI

A FastAPI + Jinja2 + Gemini-based budget and recommendation assistant matching the uploaded PocketSmart AI specification.

## Included modules

- Registration / login / logout
- Session info and session data
- User dashboard
- Home Interior Budget Planner
- Party Budget Planner
- Jewelry Budget Planner
- Optional outfit-image input for Jewelry
- Gemini-powered structured recommendations when `GEMINI_API_KEY` is configured
- Safe fallback planning when Gemini is not configured
- Recommendation history
- Marketplace search links for Amazon, Flipkart and IKEA
- Responsive HTML/CSS frontend
- `/generate-home`, `/generate-party`, `/generate-jewelry`
- `/recommendations-details`, `/history`, `/startup`, `/token`

## Run on Windows

```bat
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Gemini

Put your Gemini API key in `.env`.

The model is configurable with `GEMINI_MODEL`. The PDF names Gemini 1.5 Flash Pro; the code keeps the model configurable so you can use the model identifier available to your API account.

## Important implementation choice

The PDF mentions both Flask and FastAPI in different milestones. The later architecture explicitly specifies FastAPI routes, Uvicorn and FastAPI-based integration, so this implementation uses FastAPI as the backend while preserving `app.py` as a compatibility entry point.

No fake live inventory is claimed. Marketplace buttons open platform search URLs; exact availability and prices should be verified on the destination platform.
