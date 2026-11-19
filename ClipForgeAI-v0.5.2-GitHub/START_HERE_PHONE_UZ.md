# Eng oson boshlash — Android telefondan

**Birinchi vazifa: APK build qilish.**

1. ZIP faylni Android'da oching (Files/ZArchiver orqali).
2. GitHub ilovasi yoki brauzerda yangi **Private repository** yarating.
3. ZIP ichidagi fayllarni repository'ga yuklang. Papkalar tuzilishi aynan shunday qolishi shart: `.github`, `android`, `backend`.
4. GitHub repository ichida Actions bo'limiga kiring.
5. `Build ClipForge AI APK` workflow → `Run workflow` ni bosing.
6. Yashil belgi chiqqach, shu ishga tushirish sahifasidan `ClipForgeAI-debug-apk` artifact ZIP'ni yuklab oling.
7. ZIP ichidagi `app-debug.apk` ni o'rnating.

**Keyingi vazifa: server.** Render'da shu repository'ni ulang, Root Directory'ni `backend` qiling va Docker tanlang. Gemini API key hamda o'zingiz yaratgan API tokenni faqat Render Environment Variables ichiga kiriting.

Agar GitHub Actions qizil xato bersa, xato matnini yuboring. API key yoki maxfiy tokenni yubormang.
