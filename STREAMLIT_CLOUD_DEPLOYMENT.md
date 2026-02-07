# نشر Dahab AI على Streamlit Cloud

## الميزات الجديدة 🎉

تم تحديث البرنامج ليعمل بشكل كامل على **Streamlit Cloud** بدون الحاجة لتشغيل `worker.py` يدوياً.

### ما الذي تغير؟

1. **Worker مدمج داخل Streamlit**: تم إنشاء `streamlit_worker.py` الذي يعمل تلقائياً في الخلفية
2. **بدء تلقائي**: يبدأ Worker تلقائياً عند فتح أي صفحة
3. **Thread-based**: يعمل في خيط منفصل (background thread) متوافق مع Streamlit Cloud
4. **مستقر وآمن**: لا يتوقف بسبب مشاكل السيرفر أو الشبكة

## خطوات النشر على Streamlit Cloud

### 1. رفع الكود على GitHub

```bash
git init
git add .
git commit -m "Initial commit - Dahab AI with integrated worker"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/dahab-ai.git
git push -u origin main
```

### 2. نشر على Streamlit Cloud

1. اذهب إلى [share.streamlit.io](https://share.streamlit.io)
2. سجل دخول بحساب GitHub
3. اضغط **"New app"**
4. اختر repository الخاص بك: `YOUR_USERNAME/dahab-ai`
5. اختر branch: `main`
6. اختر main file: `app.py`
7. اضغط **"Deploy"**

### 3. انتظر النشر

- سيستغرق 2-5 دقائق
- سيتم تثبيت كل المكتبات تلقائياً من `requirements.txt`
- بمجرد الانتهاء، سيعمل البرنامج كاملاً!

## كيف يعمل Worker المدمج؟

### الآلية الجديدة

```python
# في streamlit_worker.py
class StreamlitWorker:
    """Worker يعمل في background thread"""
    
    def start(self):
        # يبدأ خيط منفصل
        self.thread = threading.Thread(
            target=self._worker_loop, 
            daemon=True
        )
        self.thread.start()
    
    def _worker_loop(self):
        # يعمل بشكل مستمر في الخلفية
        while self.running:
            # جمع الأخبار
            self._process_news()
            # تحديث الأسعار
            self._update_prices()
            # توليد التوقعات
            self._generate_forecasts()
            # إدارة الصفقات
            self._monitor_open_trades()
```

### البدء التلقائي

```python
# في كل صفحة
from streamlit_worker import ensure_worker_running

# يتأكد أن Worker يعمل
ensure_worker_running()
```

## المزايا

✅ **بدء تلقائي**: لا حاجة لتشغيل أي ملف يدوياً  
✅ **متوافق مع Streamlit Cloud**: يعمل 100% على السحابة  
✅ **مستقر**: يتعافى تلقائياً من الأخطاء  
✅ **موفر للموارد**: يستخدم thread واحد فقط  
✅ **بدون توقف**: يعمل طالما التطبيق مفتوح  

## الاختبار محلياً

قبل النشر، اختبر محلياً:

```bash
# فعّل البيئة الافتراضية
.\.venv\Scripts\Activate.ps1

# شغّل Streamlit فقط (لا حاجة لـ worker.py)
streamlit run app.py
```

البرنامج سيعمل كاملاً بدون تشغيل `worker.py` منفصل!

## استكشاف الأخطاء

### Problem: Worker لا يبدأ

**الحل**: تأكد من استيراد `ensure_worker_running()` في كل صفحة

### Problem: البيانات لا تتحدث

**الحل**: انتظر 30-60 ثانية للدورة الأولى

### Problem: أخطاء في Streamlit Cloud

**الحل**: تحقق من:
- `requirements.txt` يحتوي على كل المكتبات
- لا توجد مسارات ملفات مطلقة (absolute paths)
- Database file يُنشأ تلقائياً

## ملاحظات مهمة

⚠️ **Database**: سيُنشأ ملف `dahab_ai.db` تلقائياً في Streamlit Cloud  
⚠️ **Persistence**: البيانات ستُحذف عند إعادة نشر التطبيق (Streamlit Cloud ephemeral storage)  
⚠️ **Rate Limits**: API calls محدودة (Yahoo Finance, RSS feeds)  

## الترقية لنظام دائم

لحفظ البيانات بشكل دائم:

1. استخدم **SQLite on persistent storage** (مثل Streamlit Secrets + S3)
2. أو انقل Database إلى **PostgreSQL** (مثل Supabase مجاناً)
3. أو استخدم **Streamlit Cloud Enterprise** مع persistent volumes

## الدعم

إذا واجهت أي مشكلة:
1. تحقق من logs في Streamlit Cloud Dashboard
2. تأكد أن كل الملفات موجودة على GitHub
3. راجع هذا الدليل

---

**تم! الآن البرنامج جاهز للعمل على Streamlit Cloud بدون أي تعقيدات** 🚀
