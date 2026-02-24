# Piper REST (Separate Lightweight Service)

Bu servis XTTS'den bağımsız, ayrı bir Docker Compose ile çalışan hafif bir Piper TTS REST API'sidir.

## Endpointler
- `GET /health`
- `GET /models`
- `POST /tts` (WAV döner)
- `POST /tts_to_file` (sunucuya dosya yazar)

## Hızlı Başlangıç

1. Model dosyasını yerleştirin:
- `piper-rest/data/models/` içine bir `*.onnx` dosyası koyun.
- Varsa ilgili `*.onnx.json` config dosyasını da aynı klasöre koyun.

2. Çalıştırın:
```bash
cd piper-rest
docker compose build
docker compose up -d
```

3. Test:
```bash
curl -s http://127.0.0.1:8030/health
curl -s http://127.0.0.1:8030/models

curl -X POST "http://127.0.0.1:8030/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba, bu bir piper testidir."}' \
  --output piper_test.wav
```

## Notlar
- `speaker_id`, `length_scale`, `noise_scale`, `noise_w` parametrelerini `/tts` isteğinde verebilirsiniz.
- `PIPER_MODEL_URL` ve `PIPER_MODEL_CONFIG_URL` doluysa model otomatik indirilebilir.
