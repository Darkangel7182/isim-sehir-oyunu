# Mobil Uygulama (Capacitor) Hazırlığı

Bu repo artık Capacitor ile iOS ve Android yayın sürecine hazır bir iskelete sahiptir. Bu iskelet, canlı web sürümünü uygulama içinde açar.

## Kurulum

```bash
npm install
```

## Android / iOS Projelerini Üretme

> İlk kez çalıştırırken Android Studio ve Xcode kurulu olmalıdır.

```bash
npx cap add android
npx cap add ios
```

## Senkronizasyon

Web tarafı canlı URL üzerinden açıldığı için ek build adımı yoktur. Yine de ayarları senkronize etmek için:

```bash
npm run cap:sync
```

## Uygulamayı Açma

```bash
npm run cap:open:android
npm run cap:open:ios
```

## Notlar

- Uygulama, `https://isim-sehir-oyunu.onrender.com` adresini `capacitor.config.json` içindeki `server.url` üzerinden yükler.
- İleride tamamen yerel (offline) bir paket istersen, web çıktısını `www/` içine koyup `server.url` ayarını kaldırabilirsin.
