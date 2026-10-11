# Nour Organizer — منظم الملفات الذكي (Offline PC App)

## بيعمل ايه؟
1. يرتب Downloads/Desktop في ثانية: صور / فيديو / مستندات / برامج / صوت / مضغوط / غيره.
2. يكشف الملفات المكررة (نفس الحجم + نفس SHA256) والحذف **لسلة المهملات فقط** via `shell.trashItem` — مفيش حذف نهائي.
3. إحصائيات بصرية: ايه واكل مساحتك.
4. عربي + إنجليزي، Offline بالكامل، بدون سيرفر ولا مصاريف.

## تشغيل
```
cd apps/nour-organizer
npm install
npm test
npm start
```

## تقفيل exe لبكره
```
npm run dist
```
بيطلع NSIS installer + portable exe في `dist/` — جاهز للتوزيع المجاني.

## أمان
- يتجاهل `desktop.ini` و `thumbs.db`.
- التنظيم بيعمل معاينة (dry-run) قبل التنفيذ.
- المكرر بيحتفظ بنسخة (Keep الأولى) ويرمي الباقي Recycle Bin.
- كله local — مفيش رفع ولا نت.
