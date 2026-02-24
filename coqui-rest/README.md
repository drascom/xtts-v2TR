# Coqui TTS REST

XTTS yerine kullanılan, Coqui TTS tabanlı hafif REST servis.

## Endpointler
- `GET /health`
- `GET /voices`
- `GET /models`
- `POST /tts`
- `POST /tts_to_file`

## Kurulum
```bash
cd coqui-rest
docker compose build
docker compose up -d
```

## Test
```bash
curl -s http://127.0.0.1:8040/health

curl -X POST "http://127.0.0.1:8040/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Coqui TTS."}' \
  --output test.wav
```

## Model değiştirme
`docker-compose.yml` içindeki `COQUI_MODEL_NAME` değerini değiştirin.
Mevcut model isimlerini görmek için:
```bash
curl -s http://127.0.0.1:8040/models
```

## Not
- Bazı modeller için `speaker`, `speaker_wav` veya `language` alanları gerekir.
- `COQUI_USE_CUDA=true` yaparsanız container içinde CUDA erişimi olması gerekir.
