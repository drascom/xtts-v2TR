# Coqui TTS REST

Coqui TTS tabanli REST servis. Bu kurulumda varsayilan olarak XTTS local model modu aciktir.

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
  -d '{"text":"Merhaba dunya.","language":"tr","speaker_wav":"speaker_xtts.wav"}' \
  --output test.wav
```

## XTTS local model modu
`docker-compose.yml` varsayilanlari:
- `COQUI_MODEL_PATH=/app/data/models/XTTS-v2/model.pth`
- `COQUI_CONFIG_PATH=/app/data/models/XTTS-v2/config.json`
- `COQUI_DEFAULT_LANGUAGE=tr`
- `COQUI_DEFAULT_SPEAKER_WAV=speaker_xtts.wav`

Host tarafta dosyalar:
- `coqui-rest/data/models/XTTS-v2/model.pth`
- `coqui-rest/data/models/XTTS-v2/config.json`
- `coqui-rest/data/speakers/speaker_xtts.wav`

Bu varsayimlarla istekte yalnizca `text` gondermeniz yeterlidir:
```bash
curl -X POST "http://127.0.0.1:8040/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba dunya."}' \
  --output test.wav
```

## Not
- XTTS modunda `language` ve `speaker_wav`/`speaker` gereklidir. Varsayim env ile otomatik doldurulur.
- `COQUI_USE_CUDA=true` yaparsanız container içinde CUDA erişimi olması gerekir.
