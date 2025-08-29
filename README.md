# stefan_api_test_1 (FastAPI on Render)

Ett enkelt backend-API med volatil lagring, byggt med FastAPI och SSE för realtidsuppdateringar.

## Endpoints
- `GET /` – hälsa/status
- `GET /messages` – lista alla meddelanden (nyast först)
- `POST /messages` – skapa nytt meddelande  
  Body: `{ "text": "din text (max 1000 tecken)" }`
- `GET /stream` – Server-Sent Events (SSE) för realtidsuppdateringar  
  Klient: `new EventSource(API_BASE_URL + '/stream')`

### Datamodell
```json
{
  "id": "uuid",
  "text": "string",
  "timestamp": 1710000000.0
}
```

## Lokalt
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Öppna `http://localhost:8000/docs` för Swagger UI.

## Deploy till Render
1. Skapa en ny **Web Service** och koppla ditt repo (eller ladda upp).  
2. Render använder `render.yaml` i roten:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Python-version styrs av `runtime.txt` (3.13.0).

Din publika URL blir något i stil med:  
`https://stefan-api-test-1.onrender.com` (uppdatera i frontend).

## Enklaste säkerhet/korsdomän
CORS är öppet för alla origins för enkelhet (kan stramas åt senare).
