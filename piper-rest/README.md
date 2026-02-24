# Piper REST (Separate Lightweight Service)

Bu servis XTTS'den bağımsız, ayrı bir Docker Compose ile çalışan hafif bir Piper TTS REST API'sidir.

## Hazır 3 kadın model (`model` ile seçim)
- `tr_dfki_female`
- `en_us_amy_female`
- `en_gb_alba_female`

Model listesi endpointi:
- `GET /voices`

## Endpointler
- `GET /health`
- `GET /voices`
- `GET /models`
- `POST /tts` (WAV döner)
- `POST /tts_to_file` (sunucuya dosya yazar)

## Hızlı Başlangıç

```bash
cd piper-rest
docker compose build
docker compose up -d
```

## Test

```bash
curl -s http://127.0.0.1:8030/health
curl -s http://127.0.0.1:8030/voices
```

`model` ile seçim örneği:

```bash
curl -X POST "http://127.0.0.1:8030/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"Merhaba, Türkçe kadın model testi.",
    "model":"tr_dfki_female"
  }' \
  --output tr_test.wav

curl -X POST "http://127.0.0.1:8030/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"Hello, this is US female voice.",
    "model":"en_us_amy_female"
  }' \
  --output en_us_test.wav

curl -X POST "http://127.0.0.1:8030/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text":"Hello, this is UK female voice.",
    "model":"en_gb_alba_female"
  }' \
  --output en_gb_test.wav
```

## Notlar
- İlk kullanımda model otomatik HF'den indirilir ve `data/models` altında cache'lenir.
- İstekte `speaker_id`, `length_scale`, `noise_scale`, `noise_w` gönderilebilir.
- Özel/gated HF repo kullanıyorsanız `HF_TOKEN` ortam değişkenini doldurun.
