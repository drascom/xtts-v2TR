# Coqui TTS REST

Coqui TTS tabanli REST servis. Bu kurulumda XTTS modeli ilk acilista otomatik indirilir.

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
curl -s http://127.0.0.1:8000/health

curl -X POST "http://127.0.0.1:8000/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba dunya.","language":"tr","speaker_wav":"speaker_xtts.wav"}' \
  --output test.wav
```

## XTTS local model modu
`docker-compose.yml` varsayilanlari:
- `COQUI_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2`
- `COQUI_MODEL_PATH=` (bos)
- `COQUI_CONFIG_PATH=` (bos)
- `COQUI_DEFAULT_LANGUAGE=tr`
- `COQUI_DEFAULT_SPEAKER_WAV=speaker_xtts.wav`

Host tarafta gerekli speaker dosyasi:
- `coqui-rest/data/speakers/speaker_xtts.wav`

Bu varsayimlarla istekte yalnizca `text` gondermeniz yeterlidir:
```bash
curl -X POST "http://127.0.0.1:8000/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba dunya."}' \
  --output test.wav
```

## Not
- Servis `8000` portunda calisir.
- XTTS modunda `language` ve `speaker_wav`/`speaker` gereklidir. Varsayim env ile otomatik doldurulur.
- `COQUI_USE_CUDA=true` yaparsanız container içinde CUDA erişimi olması gerekir.
