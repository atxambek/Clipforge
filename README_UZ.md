# ClipForge AI v0.5.2 — yagona GitHub repository

Bu paket Android ilovasi va backendni bitta GitHub repository ichida saqlash uchun tayyorlangan. APK hali build qilinmagan; server ham deploy qilinmagan.

## Telefonda GitHub'ga yuklash

1. ZIP'ni oching.
2. GitHub'da yangi **Private** repository yarating (masalan `clipforge-ai`).
3. ZIP ichidagi barcha fayl va papkalarni repository ildiziga yuklang. `.github/workflows/build-android.yml` yashirin papkasini ham qo'shing.
4. GitHub → Actions → **Build ClipForge AI APK** → **Run workflow**.
5. Build muvaffaqiyatli tugagach, Actions run sahifasidagi Artifacts'dan `ClipForgeAI-debug-apk` ZIP'ni yuklab oling va ichidagi `app-debug.apk` ni telefonga o'rnating.

## Backend deploy (Render)

1. Render'da New → Web Service → GitHub repository tanlang.
2. **Root Directory**: `backend`.
3. Runtime: Docker.
4. Environment variables:
   - `GEMINI_API_KEY`: Google AI Studio'da yaratilgan API key
   - `API_ACCESS_TOKEN`: o'zingiz yaratgan uzun tasodifiy maxfiy token
   - `APP_ENV`: `production`
   - `DATABASE_PATH`: `/var/data/clipforge.db`
   - `ARTIFACTS_DIR`: `/var/data/artifacts`
   - `GEMINI_MODEL`: `gemini-3.8-flash` (akkauntingizda mavjud bo'lmasa, AI Studio'dagi mavjud model nomini kiriting)
5. Persistent disk ulang: mount path `/var/data`. Narxni tasdiqlashdan oldin Render tarifini tekshiring; doimiy disk va hosting pullik bo'lishi mumkin.
6. Deploy tugagach `https://SIZNING-SERVER.onrender.com/health` ni oching. `ok: true` qaytsa backend ishlayapti.

## Ilovani backend'ga ulash

Android ilovasida backend URL (oxirida `/docs` yoki `/health` bo'lmasin) va `API_ACCESS_TOKEN` ni kiriting. API tokenni hech qachon GitHub'ga yozmang yoki chatga yubormang.

## Muhim cheklovlar

- Google Flow promptlarini ilova yaratadi, lekin Flow'da video generatsiyasi va kliplarni upload qilish hozircha qo'lda.
- Audio fayl upload qilinmasa, yakuniy MP4 ovozsiz bo'ladi.
- 1080p — eksport o'lchami; past aniqlikdagi manbadan haqiqiy 1080p detal hosil bo'lmaydi.
- Bu prototip; production uchun navbat, autentifikatsiya/foydalanuvchi ajratish, monitoring, backup va upload himoyasini kuchaytirish kerak.
