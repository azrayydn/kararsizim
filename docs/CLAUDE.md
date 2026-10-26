# Kararsızım — Proje Planı (Claude Code için)

> Bu dosya projenin tek kaynağıdır (`docs/CLAUDE.md`). Claude Code her oturumda önce bu dosyayı okumalı, sadece **istenen fazı** uygulamalı, bir sonraki faza kendiliğinden geçmemelidir. Dosya `docs/` içinde olduğu için Claude Code onu otomatik yüklemez; her oturumda açıkça okunmalıdır.

---

## 1. Proje Özeti

**Kararsızım**, insanların kararsız kaldığı konularda diğer kullanıcılara danışabildiği bir anket platformudur.

Örnek: Kullanıcı "Bugün sinemaya mı gitsem, restorana mı?" diye bir soru sorar, seçenekleri ekler ("Sinema", "Restoran", "Evde film"), diğer kullanıcılar oy verir.

### Temel kurallar

- Bir ankette **en az 2, en fazla 5** seçenek olur.
- **Takip (follow) mekanizması yoktur.** Akış, tüm anketlerin yeni → eski sıralı listesidir.
- Her anket herkese açıktır.
- **Üye olmayan** ziyaretçiler anketleri ve sonuçları **görüntüleyebilir**.
- **Anket oluşturmak ve oy vermek için üye girişi gerekir** (KESİN KARAR: bir kişi bir ankete tek oy verebilsin diye üyesiz oy yoktur).
- **Sonuçlar herkese, her zaman görünür** (KESİN KARAR): ziyaretçiler de oy vermeden sonuçları görebilir.
- Kayıtta **e-posta, parola ve kullanıcı adı** alınır.
- Anketlerde sadece **kullanıcı adı** görünür. **E-posta hiçbir yerde, hiçbir sayfada ve hiçbir yanıtta gösterilmez.**
- Bu bir **prototiptir**. Basit tut, gereksiz karmaşıklık ekleme.

---

## 2. Teknoloji Yığını

| Katman | Seçim |
|---|---|
| Dil | Python 3.12+ (Django 6.x gerektirir) |
| Backend | Django (güncel kararlı sürüm) |
| Veritabanı | Supabase (yönetilen PostgreSQL) — Django ORM ile bağlanılır |
| Deployment | Vercel |
| Frontend | Django template'leri + saf HTML, CSS, JavaScript (aynı repo, ayrı framework yok) |
| Statik dosyalar | WhiteNoise |
| Testler | Yerelde SQLite (sadece test için, bkz. bölüm 7) |

### Bilinçli kararlar (prototipi basit tutmak için)

- **Kimlik doğrulama Django'nun kendi auth sistemi ile yapılır.** Supabase Auth KULLANILMAZ. Supabase sadece PostgreSQL sağlayıcısıdır.
- **Django REST Framework, React, Tailwind, Celery, Redis vb. KULLANILMAZ.**
- JavaScript yalnızca küçük iyileştirmeler içindir (seçenek ekle/çıkar, oy sonrası sonuç çubuklarını güncelleme). Sayfalar sunucu tarafında render edilir.
- Oy verme, küçük bir `fetch` ile JSON döndüren tek bir endpoint kullanabilir; JS çalışmazsa normal form gönderimi de çalışmalıdır (tercih edilen yol).

---

## 3. Veri Modeli

Django'nun `AbstractUser` sınıfından türeyen özel bir kullanıcı modeli kullanılır. **Bu model ilk migration'dan önce tanımlanmalıdır** (sonradan değiştirmek zordur).

### `User` (accounts uygulaması)

- `username` — benzersiz, 3–20 karakter, sadece İngilizce harf (a-z), rakam ve alt çizgi (Türkçe karakter ve boşluk yok), büyük-küçük harf duyarsız benzersizlik
- `email` — benzersiz (küçük harfe çevrilerek saklanır), zorunlu
- `password` — Django'nun standart hash'i
- `date_joined` — Django'dan gelir
- Giriş **e-posta + parola** ile yapılır (`USERNAME_FIELD = "email"`). `username` herkese görünen takma addır.
- `REQUIRED_FIELDS = ["username"]` olmalı (aksi halde `createsuperuser` çalışmaz).
- E-posta ile giriş yapıldığı için **özel bir `UserManager`** (`BaseUserManager` veya `UserManager` türevi: `create_user` ve `create_superuser` e-postayı kimlik olarak alır) yazılmalı.
- Kullanıcı adı büyük-küçük harf duyarsız benzersizliği için veritabanı seviyesinde `UniqueConstraint(Lower("username"), name=...)` kullanılmalı; e-posta kaydedilmeden önce küçük harfe çevrilmeli.
- Django admin'de `UserAdmin` özel modele uyarlanmalı.

### `Poll` (polls uygulaması)

- `author` — FK → User (`on_delete=CASCADE`)
- `question` — CharField, maks 200 karakter, zorunlu
- `created_at` — otomatik
- `closes_at` — boş olabilir; doluysa anket bir **Acil Karar**'dır (oluşturulma + 5 dk)
- `settled_at`, `winner` — süresi dolan Acil Karar kesinleşince (tembel, ilk ziyarette) doldurulur; `winner` beraberlikte veya 5'ten az oyda boş kalır

### `Option`

- `poll` — FK → Poll (`related_name="options"`, `on_delete=CASCADE`)
- `text` — CharField, maks 100 karakter, zorunlu
- `position` — küçük tamsayı (sıralama için)

### `Vote`

- `poll` — FK → Poll
- `option` — FK → Option
- `user` — FK → User
- `created_at` — otomatik
- **Kısıtlama:** `UniqueConstraint(fields=["poll", "user"])` → bir kullanıcı bir ankete yalnızca bir oy verir.
- Oyun seçeneği o ankete ait olmalıdır (view/form içinde doğrulanır).

### Doğrulama kuralları

- Bir ankette seçenek sayısı **2 ≤ n ≤ 5** olmalı (form seviyesinde doğrula; boş seçenekleri say).
- Aynı ankette aynı metinli iki seçenek olmasın (büyük-küçük harf duyarsız).
- Soru ve seçenekler baştaki/sondaki boşluklardan arındırılır.

---

## 4. Sayfalar ve URL'ler

| URL | Erişim | Açıklama |
|---|---|---|
| `/` | Herkes | Anket akışı (yeni → eski), sayfalama (sayfa başına 10–20) |
| `/anket/<id>/` | Herkes | Anket detayı: soru, seçenekler, yazar kullanıcı adı, tarih, sonuçlar |
| `/anket/yeni/` | Giriş zorunlu | Anket oluşturma formu (2–5 seçenek, JS ile ekle/çıkar) |
| `/anket/<id>/oy/` | Giriş zorunlu, POST | Oy verme |
| `/anket/<id>/sil/` | Sadece sahibi, POST | Kendi anketini silme |
| `/kayit/` | Giriş yapmamış | Kayıt (kullanıcı adı, e-posta, parola, parola tekrar) |
| `/giris/` | Giriş yapmamış | Giriş (e-posta + parola) |
| `/cikis/` | POST | Çıkış |
| `/ben/` | Giriş zorunlu | Kendi oluşturduğum anketler listesi |

### Davranış detayları

- Giriş yapmamış biri "Anket Oluştur" veya "Oy Ver" ile karşılaşırsa giriş sayfasına yönlendirilir ve girişten sonra geldiği sayfaya (`next`) döner.
- Sonuçlar herkese gösterilir: her seçenek için oy sayısı ve yüzde çubuğu.
- Oy vermiş kullanıcıya kendi seçtiği seçenek işaretli gösterilir; tekrar oy verme formu gösterilmez.
- Anket detayında yazar **sadece kullanıcı adıyla** gösterilir.
- Oy sayıları tek sorguda hesaplanmalı (`annotate(Count(...))`), N+1 sorgu olmamalı.
- Arayüz dili **Türkçe**, `LANGUAGE_CODE = "tr"`, `TIME_ZONE = "Europe/Istanbul"`.

---

## 4.1 Tasarım ve Arayüz Yönergeleri

**Hedef kitle:** Gençler (yaklaşık 16–28 yaş), ağırlıklı olarak telefondan girecek.
**Hissiyat:** Modern, sade, enerjik, eğlenceli ama kalabalık değil. Bir "form sitesi" değil, Instagram hikayesi anketi kadar hafif ve hızlı hissettirmeli.

### Genel ilkeler

- **Mobil öncelikli (mobile-first).** Önce 360–430px genişlik için tasarla, sonra masaüstüne genişlet. İçerik masaüstünde ortada, dar bir sütunda (maks ~640px) durur; yan boşluklar bol olur.
- **Sade:** Sayfa başına tek ana eylem. Gereksiz kenarlık, gölge ve süs yok.
- **Bol boşluk, büyük ve net tipografi.** Soru metni sayfanın kahramanı olmalı.
- **Tek bir yumuşak vurgu rengi (adaçayı yeşili), gradyan yok.** Mor/pembe tonlar kullanılmaz ("yapay zeka" havası verdiği için). Renk sadece önemli şeyleri (butonlar, seçili seçenek, sonuç çubukları) vurgulasın.
- Harici CSS/JS framework'ü (Bootstrap, Tailwind vb.) **kullanılmaz**; her şey `style.css` içinde, CSS değişkenleriyle yazılır.

### Görsel stil

| Öğe | Yönerge |
|---|---|
| Font | Google Fonts'tan tek aile: **Plus Jakarta Sans** (alternatif: Inter). Başlıklar kalın (700–800), gövde 400–500. Yedek: `system-ui, sans-serif` |
| Renkler | **Sadece açık, ferah tema** (koyu tema YOK, sistem koyu modda olsa bile). Bol boşluk, çok açık zemin |
| Vurgu | Adaçayı yeşili `#4E7D68` (hover `#3B6452`), düz renk. Beyaz yazı kontrastı ≥ 4.5 |
| Zemin | Soluk yeşil-gri `#E8EDE5` (beyaz DEĞİL); kartlar sıcak kırık beyaz `#FAFBF8`; üstte çok hafif aydınlık ışıma |
| Köşeler | Yuvarlak: kartlar `16–20px`, butonlar ve seçenekler `12–999px` (hap/pill) |
| Gölge | Çok hafif, yumuşak gölge; sert çizgi kenarlık yok |
| İkon | Kütüphane yok. Gerekirse emoji veya inline SVG |
| Logo | `static/img/logo.svg`: adaçayı yeşili yuvarlak kare içinde ikiye ayrılan yol (kararsızlık / iki seçenek), uçlarında biri beyaz biri şeftali rengi iki daire. Yanında küçük harfli "kararsızım" yazısı; aynı dosya favicon olarak da kullanılır. Emoji veya robot/yapay zeka görseli kullanılmaz |

Tüm renk, yarıçap ve boşluk değerleri `:root` altında **CSS değişkeni** olarak tanımlanmalı (`--bg`, `--card`, `--text`, `--muted`, `--accent`, `--accent-2`, `--radius`, ...) ki tema sonradan kolayca değişsin.

### Bileşenler

- **Üst çubuk:** Yapışkan (sticky), sade; solda logo, sağda giriş/kayıt veya kullanıcı adı. Hafif bulanık arka plan (`backdrop-filter`) olabilir.
- **Anket kartı (ana sayfa):** Soru büyük ve kalın; altında seçeneklerin küçük önizlemesi (hap şeklinde etiketler), yazar `@kullaniciadi`, "2 saat önce" gibi göreli zaman, toplam oy sayısı. Karta tıklayınca detaya gider. Üzerine gelince hafif yukarı kalkma (hover).
- **Oy verme (detay sayfası):** Seçenekler büyük, dokunması kolay (en az 48px yükseklik) tam genişlikte butonlar/kartlardır. Seçilince vurgu rengiyle belirgin hale gelir.
- **Sonuçlar:** Oy verdikten sonra seçenek kartlarının içinde **yatay yüzde çubukları** animasyonla dolar (≈600ms, `ease-out`). Kazanan seçenek hafifçe vurgulanır, kullanıcının kendi seçimine küçük bir ✓ konur. Yüzdeler büyük ve okunaklı.
- **Anket oluşturma formu:** Büyük bir soru alanı ("Ne konuda kararsızsın?"), altında seçenek alanları; "+ Seçenek ekle" butonu (5'e gelince pasifleşir ve "en fazla 5" bilgisi görünür), seçeneklerde küçük "×" silme butonu (2'ye inince gizlenir). Karakter sayacı göster.
- **Tek "Anket aç" girişi (FAB):** Sağ altta sabit buton; telefonda yuvarlak "+", geniş ekranda "+ Anket aç" yazılı hap. Giriş yapmamışsa girişe yönlendirir. **Sayfada başka hiçbir yerde ikinci bir "Anket aç" butonu OLMAZ** (üst çubukta, başlık altında, yan panelde, boş durumlarda yok). Anket formunda ve giriş/kayıt sayfalarında gizlenir.
- **Giriş/Kayıt sayfaları:** Ortada tek kart, az alan, büyük butonlar, net hata mesajları (kırmızı yerine yumuşak mercan tonu).
- **Boş durum ve hata sayfaları:** Eğlenceli, kısa, emojili mesajlar.

- **Yan paneller (sadece ≥1100px ekranlarda, telefonda gizli):** Sayfa 3 sütun olur. Solda "Nasıl çalışır?" (3 adım) ve sayılar (anket / oy / üye); sağda "Popüler anketler" (en çok oy alan 5 anket, oy sayısı sıfır olanlar hariç). Paneller sayfayla birlikte kayar (sticky). Hiçbir panelde e-posta veya kişisel veri yok.

- **Anket özeti kartı (anket detay sayfasında, oy varsa):** Sonuçların altında, `static/img/yorum.svg` (gülümseyen konuşma balonu) maskotlu yumuşak yeşil kart. İçinde bir "ruh hali" etiketi (Kıran kırana, Net karar, Tam beraberlik, Fikirler dağınık, Oybirliği, Isınıyoruz...), 1-2 cümlelik samimi yorum, oy vermiş kullanıcıya kişisel bir satır ("Sen de çoğunluğun yanındasın 🤝") ve "N oya göre" notu. **Metinler `polls/insights.py` içindeki kurallarla üretilir, gerçek bir yapay zeka modeli DEĞİLDİR; bu yüzden kartta "yapay zeka" yazmaz.** Seçenek metinleri kısaltılır ve şablonda kaçışlanır; kimsenin tekil oyu veya e-postası gösterilmez.
- **Bildirimler (toast):** Django mesajları ("Anketin silindi.", "Oyun kaydedildi!" vb.) sayfa içinde gri çubuk olarak DEĞİL, **sağ üstte (telefonda üst ortada) kayan toast kartı** olarak görünür (`static/js/toast.js`): başarıda ~4,5 sn, hatada ~7 sn sonra kendiliğinden kaybolur, üzerine gelince/odaklanınca süre durur, × ile hemen kapanır, altında kalan süreyi gösteren ince çubuk vardır. Hata toast'ları `role="alert"`'tir. Hareket azaltma tercihinde animasyon kapanır.
- **Rozet kartı yerleşimi:** "Anketlerim" sayfasında orta alan sadece kullanıcının anket listesine ayrılır. Rozet kartı geniş ekranda **sağ panelde, "Popüler anketler"in altında** durur; panel ekrandan uzunsa kendi içinde kayar. Panellerin gizlendiği dar ekranlarda (telefon) listenin üstünde tek satırlık, dokununca açılan bir özet (`<details>`) gösterilir.

### Mikro-etkileşimler (hafif tut)

- Butonlara basınca küçük ölçek efekti (`transform: scale(.98)`), hover'da hafif parlama.
- Sayfa geçişlerinde ağır animasyon yok; sadece kartların hafif belirme (fade-in) animasyonu olabilir.
- Her animasyon `@media (prefers-reduced-motion: reduce)` içinde kapatılmalı.
- Oy verildiğinde yüzde çubuklarının dolması en önemli "wow" anıdır; geri kalanı sade kalsın.

### Dil ve ton (arayüz metinleri Türkçe)

Samimi, kısa, sen dili. Örnekler:

- Ana sayfa başlığı: **"Kararsız mısın? Sor, millet karar versin."**
- Anket oluştur butonu: **"Anket aç"**
- Soru alanı placeholder'ı: **"Bugün sinemaya mı gitsem, restorana mı?"**
- Oy ver butonu: **"Oyumu kullan"**
- Boş akış: **"Henüz kimse kararsız kalmamış 😄 İlk anketi sen aç!"**
- Giriş gerektiren işlemde: **"Oy vermek için önce giriş yapmalısın."**

### Erişilebilirlik (asgari)

- Metin/arka plan kontrastı yeterli olmalı (gradyan üzerindeki metin dahil, beyaz metin koyu tonlarda).
- Tüm butonlar ve linkler klavye ile odaklanabilir, görünür `:focus-visible` çerçevesi var.
- Form alanlarında `label` bulunur; resim yerine kullanılan emoji'ler anlam taşıyorsa `aria-label` verilir.
- Dokunmatik hedefler en az 44–48px.

---

## 5. Proje Yapısı

```
kararsizim/
├── docs/
│   └── CLAUDE.md             # bu dosya
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── config/                   # Django proje ayarları
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                 # özel User modeli, kayıt/giriş/çıkış
├── polls/                    # Poll, Option, Vote, view'lar, form'lar
├── templates/
│   ├── base.html
│   ├── accounts/
│   └── polls/
└── static/
    ├── css/style.css
    └── js/
        ├── poll_form.js      # seçenek ekle/çıkar
        └── vote.js           # (opsiyonel) fetch ile oy
```

---

## 6. Ortam Değişkenleri (`.env.example`)

```
SECRET_KEY=degistir-beni
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
DATABASE_URL=postgresql://postgres.xxxx:PAROLA@aws-0-xx.pooler.supabase.com:6543/postgres
# Migration için (session pooler, port 5432); yoksa DATABASE_URL kullanılır:
MIGRATION_DATABASE_URL=
```

- **İki ayrı Supabase projesi vardır:** geliştirme (`.env` içinde) ve canlı (sadece Vercel ortam değişkenlerinde). Canlı projenin bağlantı bilgisi yerel `.env` dosyasına **yazılmaz**.

- `.env` dosyası **asla** git'e eklenmez (`.gitignore`'a yaz).
- Ayarlar `os.environ` ile okunur. `dj-database-url` kullanılabilir.
- `SECRET_KEY` koda gömülmez.

---

## 7. Supabase + Django Notları

1. Supabase'de yeni proje oluştur, bağlantı bilgisini **Connect** bölümünden al.
2. Vercel serverless olduğu için **pooler (transaction mode, port 6543)** bağlantısı kullan.
3. Django ayarlarında transaction pooler ile uyum için:
   - `DISABLE_SERVER_SIDE_CURSORS = True`
   - `CONN_MAX_AGE = 0`
4. **Migration'lar yerelde çalıştırılır** (`python manage.py migrate`), Vercel build/çalışma sırasında değil. Önce geliştirme projesine uygulanır; canlıya yayın öncesi, canlı projenin bağlantısı geçici olarak (komut satırında, dosyaya yazmadan) kullanılarak aynı migration'lar uygulanır.
   - Migration için transaction pooler (6543) yerine **session pooler (5432)** tercih edilir. Direct bağlantı bazı internet bağlantılarında IPv6 gerektirdiği için çalışmayabilir. **Faz 0'da hangisinin çalıştığı denenerek doğrulanır.**
   - Testler **yerelde SQLite ile** çalışır (ayrı bir `settings_test.py` veya ortam değişkeniyle). Django'nun test veritabanı oluşturması Supabase üzerinde izin sorunu çıkarabilir; testler Supabase'e bağlanmamalıdır.
5. **Güvenlik:** Django tabloları Supabase'in `public` şemasında oluşur ve Supabase Data API (PostgREST) üzerinden erişilebilir hale gelebilir. Bunu engellemek için ya Data API'yi kapat, ya da tüm tablolarda RLS'i etkinleştir (politika ekleme; Django doğrudan Postgres rolü ile bağlandığı için etkilenmez). Özellikle `accounts_user` tablosu (e-posta ve parola hash'i) dışarı açık olmamalı.
6. Supabase bağlantı parolası yalnızca ortam değişkeninde durur.

---

## 8. Vercel Deployment Notları

(Vercel'in resmi Django rehberine göre doğrulandı, Ekim 2026.)

- Vercel, `manage.py` dosyasını bulup `DJANGO_SETTINGS_MODULE`'ü okur ve giriş noktasını `settings.py` içindeki `WSGI_APPLICATION` değerinden (`config.wsgi.application`) bulur. **`vercel.json` ve `app = application` satırı GEREKMEZ.**
- Bağımlılıklar `requirements.txt` içinden kurulur; Python sürümü `.python-version` dosyasından okunur (Vercel'de 3.12, 3.13, 3.14 desteklenir; Django 6.x için ≥3.12 şart).
- `STATIC_ROOT` tanımlı olduğu için Vercel build sırasında `collectstatic`'i **kendisi** çalıştırır ve dosyaları CDN'den `/static/` adresinde sunar (WhiteNoise `CompressedManifestStaticFilesStorage` desteklenir). Build komutuna `collectstatic` yazılmaz.
- **Build sırasında `settings.py` içe aktarıldığı için `SECRET_KEY` ve `DATABASE_URL` ortam değişkenleri ilk deploy'dan ÖNCE Vercel'de tanımlı olmalıdır**, yoksa build hata verir (bilinçli: eksik ayar sessizce yanlış veritabanına bağlanmasın).
- Vercel'de ortam değişkenleri: `SECRET_KEY` (canlıya özel, geliştirmedekinden farklı), `DEBUG=False`, `DATABASE_URL` (canlı Supabase, **transaction pooler 6543**), `ALLOWED_HOSTS=.vercel.app`, `CSRF_TRUSTED_ORIGINS=https://*.vercel.app` (özel alan adı eklenirse ikisine de eklenir).
- Production'da `SECURE_PROXY_SSL_HEADER` açıktır (Vercel HTTPS'i önde sonlandırır); `SESSION_COOKIE_SECURE` ve `CSRF_COOKIE_SECURE` açıktır.
- SQLite kullanılmaz; migration'lar Vercel'de değil yerelde çalıştırılır (bölüm 7).

---

## 9. Güvenlik Kontrol Listesi (prototip için asgari)

- CSRF koruması açık; tüm POST formlarında `{% csrf_token %}`.
- Şablonlarda otomatik kaçış (autoescape) açık bırakılır; `|safe` kullanılmaz.
- Parolalar Django'nun varsayılan hash'i ile saklanır; Django parola doğrulayıcıları açık.
- E-posta hiçbir şablonda, JSON yanıtında veya URL'de görünmez. (Not: giriş yapmış kullanıcı için dahi sayfalarda e-posta göstermeye gerek yok.)
- Silme ve oy verme yalnızca POST ile yapılır; silmede sahiplik kontrolü yapılır (başkasının anketi silinemez → 403/404).
- Oy verme sırasında `IntegrityError` yakalanır (çift oy yarışı) ve kullanıcıya anlaşılır mesaj gösterilir.
- Production'da: `DEBUG=False`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`.

---

## 10. Fazlar

Her faz bittiğinde: çalıştır, test et, kısa bir özet ver ve **dur**. Bir sonraki faza ancak kullanıcı isterse geç.

### Faz 0 — İskelet ve veritabanı bağlantısı

**Yapılacaklar**
- Sanal ortam, `requirements.txt` (`django`, `psycopg[binary]`, `dj-database-url`, `whitenoise`, `python-dotenv` veya benzeri).
- `config` projesi, `accounts` ve `polls` uygulamaları.
- `settings.py`: ortam değişkenleri, Supabase bağlantısı (bölüm 7), Türkçe dil/saat dilimi, `templates/` ve `static/` yolları, WhiteNoise.
- `.gitignore`, `.env.example`.
- `base.html` (font bağlantısı, viewport meta etiketi, sticky üst çubuk iskeleti) ve `style.css` içinde **tasarım temeli**: bölüm 4.1'deki CSS değişkenleri (renk, yarıçap, boşluk), açık tema, tipografi, buton ve kart temel stilleri. Sonraki fazlardaki tüm sayfalar bu temeli kullanır.
- Ana sayfada "Kararsızım" başlığı ve slogan içeren basit bir sayfa (tasarım temelinin çalıştığını göstermek için).

- Supabase **geliştirme** projesine bağlantıyı dene (basit bir `SELECT 1`); migration için hangi bağlantının (session pooler 5432 / transaction pooler 6543) çalıştığını doğrula ve sonucu raporla.
- Test ayarları: SQLite ile çalışan ayrı test yapılandırması.

**Bitiş ölçütü:** `python manage.py runserver` ile ana sayfa açılır; `python manage.py check` hatasız; Django Supabase geliştirme veritabanına bağlanabiliyor.

> ⚠️ **Faz 0'da `migrate` ÇALIŞTIRILMAZ.** Özel `User` modeli (Faz 1) ilk `migrate`'den ÖNCE tanımlanmalıdır; ilk migrate Faz 1'in sonunda yapılır.

### Faz 1 — Üyelik sistemi

**Yapılacaklar**
- Özel `User` modeli ve `UserManager` (bölüm 3), `AUTH_USER_MODEL`, ilk migration ve **ilk `migrate`** (geliştirme veritabanında).
- Admin panelinde özel User'ı yönetme ve `createsuperuser` ile süper kullanıcı oluşturma çalışmalı.
- Kayıt, giriş, çıkış view'ları ve şablonları; formlarda Türkçe hata mesajları.
- Kullanıcı adı ve e-posta benzersizlik ve biçim doğrulaması (büyük-küçük harf duyarsız).
- Üst menü: giriş yapmamışsa "Giriş / Kayıt", yapmışsa kullanıcı adı + "Çıkış".
- `first_name` ve `last_name` alanları kaldırıldı (kullanılmıyor); kayıt sonrası kullanıcı otomatik giriş yapar ve `next` adresine (güvenliyse) yönlendirilir.

**Bitiş ölçütü:** Kayıt ol → çıkış yap → e-posta ve parola ile giriş yap akışı çalışır. Aynı e-posta veya kullanıcı adıyla ikinci kayıt reddedilir.

### Faz 2 — Anket oluşturma ve listeleme

**Yapılacaklar**
- `Poll`, `Option` modelleri ve migration.
- Anket oluşturma formu: soru + dinamik seçenek alanları (başlangıçta 2, JS ile 5'e kadar eklenebilir, 2'ye kadar silinebilir). Sunucu tarafında 2–5 doğrulaması (JS'e güvenme).
- Ana sayfa akışı (yeni → eski, sayfalı), anket kartında soru, yazar kullanıcı adı, göreli/mutlak tarih, seçenek sayısı.
- Anket detay sayfası (şimdilik sonuçsuz, seçenekler listelenir).
- Giriş yapmamış biri `/anket/yeni/` adresine giderse girişe yönlendirilir.
- Tüm sayfalar baştan itibaren bölüm 4.1'e göre tasarlanır: anket kartları, oluşturma formu, mobil "+" butonu, üst çubuk.

**Bitiş ölçütü:** Giriş yapmış kullanıcı anket oluşturur; anket ana sayfada ve detayda görünür; ziyaretçi görüntüleyebilir ama oluşturamaz.

### Faz 3 — Oy verme ve sonuçlar

**Yapılacaklar**
- `Vote` modeli, `UniqueConstraint`, migration.
- Oy verme endpoint'i (POST, giriş zorunlu, seçeneğin ankete ait olduğunu doğrula).
- Detay sayfasında sonuçlar: oy sayısı + yüzde çubuğu; toplam oy sayısı.
- Oy vermiş kullanıcıya kendi seçimi işaretli; tekrar oy formu yok.
- Ana sayfa kartlarında toplam oy sayısı.
- Sonuç çubukları bölüm 4.1'deki gibi animasyonla dolar; kullanıcının seçimi ✓ ile işaretlenir.
- Opsiyonel: `vote.js` ile sayfa yenilemeden sonuç güncelleme (form yedek olarak çalışmaya devam eder).

**Bitiş ölçütü:** İki farklı kullanıcı aynı ankete oy verir, sonuçlar doğru görünür; aynı kullanıcı ikinci kez oy veremez; ziyaretçi sonuçları görür ama oy veremez.

### Faz 4 — Arayüz cilası ve küçük özellikler

**Yapılacaklar**
- Bölüm 4.1'deki tasarım yönergelerine göre arayüzün son cilası: mikro-etkileşimler, `prefers-reduced-motion`, odak çerçeveleri, 360px ve 430px genişliklerde mobil kontrol, eğlenceli Türkçe arayüz metinleri ve boş durumlar.
- "Anketlerim" sayfası (`/ben/`) ve kendi anketini silme (onay penceresiyle, POST).
- Boş durumlar ("Henüz anket yok"), form hata mesajlarının düzgün gösterimi, başarı mesajları (Django messages).
- Özel 404 ve 500 sayfaları.
- Temel testler (SQLite ile, Supabase'e bağlanmadan): model doğrulamaları, tek oy kuralı, yetki kontrolleri (silme, oluşturma, oy verme), e-postanın sayfalarda görünmemesi, kullanıcı adı/e-posta büyük-küçük harf benzersizliği.

**Bitiş ölçütü:** Uygulama telefonda ve masaüstünde düzgün görünür; testler geçer.

### Faz 5 — Vercel'e yayın

**Yapılacaklar**
1. Projeyi GitHub'a (özel/private depo) yükle. `.env`, `.venv` ve `.zip` dosyaları yüklenmez (`.gitignore`).
2. Canlı Supabase projesinde tabloları oluştur: yerelde, geçici ortam değişkeniyle `python manage.py migrate --settings=config.settings_migrate` (session pooler 5432); canlı bağlantı bilgisi hiçbir dosyaya yazılmaz.
3. Canlı projede `docs/supabase_rls.sql` dosyasını SQL Editor'de çalıştır (Data API üzerinden tablo erişimini kapatır) ve canlı için `createsuperuser` ile yönetici hesabı oluştur.
4. Vercel'de depoyu içe aktar, **deploy'dan önce** ortam değişkenlerini gir (bölüm 8), sonra deploy et.
5. Yayın sonrası kontrol listesi: kayıt, giriş, anket aç, oy ver, çıkış, anket sil, olmayan bir adres (404 sayfası), yönetici paneli (`/admin/`), telefonda görünüm.

**Bitiş ölçütü:** Canlı Vercel adresinde tüm temel akış çalışır.

---

### Acil Karar ve Rozetler (yapıldı, Faz 5'ten önce eklendi)

**Acil Karar:** Anket oluştururken "Acil Karar yap" kutusu işaretlenirse anket **5 dakika** açık kalır (`URGENT_MINUTES`).
- **Oy verme sunucuda kilitlenir:** süre dolunca oy verilemez ("Bu Acil Karar'ın süresi doldu"). Sayaç sadece görüntüdür; kural sunucu saatiyle işler.
- **Süre dolana kadar KİMSE sonucu göremez** (yüzde, oy sayısı, çubuk, özet kartı sayfaya hiç yazılmaz; sadece "N kişi oy verdi" görünür). Oy vermiş kişi sadece kendi seçimini ✓ ile görür. Bu, herkesin sonucu görüp kazananı taklit etmesini önler ve rozetleri anlamlı kılar. Normal anketlerde sonuçlar her zaman herkese açık kalır.
- Süre dolunca sayaç sıfırlanır, sayfa bir kez yenilenir, sonuçlar açılır ve **kilitlenir** ("Oylama kapandı, sonuç kilitlendi"). Özet kartı "Süre doldu!" diye başlar.
- Akıştaki kartlarda canlı geri sayım çipi ("⏱ Acil Karar · 3:42") veya "🔒 Kapandı" görünür.

**Rozetler (`polls/badges.py`):** Süresi dolmuş, **en az 5 oy** almış ve **net bir kazananı olan** (beraberlik yok) Acil Karar anketlerinde, kazanan seçeneğe oy veren kişi "isabet" sayar. Kendi anketine verilen oy sayılmaz, normal anketler sayılmaz. Rozet için hem yeterli sayıda oy hem yeterli isabet oranı gerekir:

| Rozet | Koşul |
|---|---|
| 🐣 Karar Çırağı | en az 3 sayılan oy |
| 🎯 Karar Verici | en az 8 oy ve %55 isabet |
| 🏅 Master Karar Verici | en az 20 oy ve %65 isabet |
| 🧙 Guru | en az 40 oy ve %75 isabet |

Rozet emojisi anketlerde `@kullaniciadi` yanında görünür (herkese açık sadece rozet adı); sayılar ve oran yalnızca kişinin kendi "Anketlerim" sayfasında görünür. Bireysel oylar hiçbir yerde gösterilmez. Kesinleşme (`settle_due_polls`) ilk ziyarette tembel çalışır; zamanlanmış görev gerekmez.

**Bilinen sınırlar:** E-posta doğrulaması olmadığı için sahte hesaplarla rozet şişirilebilir; kaç Acil Karar açılabileceğine sınır yoktur (hız sınırı sonraki aşama).

---

### Faz 6 — Anket fotoğrafı (yapıldı, Faz 5'ten önce)

Her ankete en fazla **1 isteğe bağlı fotoğraf** eklenebilir (seçeneklere ayrı fotoğraf yok).

- **Depolama kararı (prototip):** Fotoğraflar **Supabase Storage'da değil, veritabanında** (`PollImage.data`, ayrı tablo) saklanır; böylece ek servis/anahtar gerekmez ve normal anket sorguları görsel baytlarını hiç yüklemez (`Poll.has_image` bayrağı kullanılır). Fotoğraf `/anket/<id>/foto/` adresinden sunulur. **Sınır:** Supabase ücretsiz planda veritabanı 500 MB'tır; işlenmiş bir fotoğraf genelde 50-300 KB'tır (yaklaşık 2000+ fotoğraf). Büyüyünce Supabase Storage'a geçilir (veri taşıma gerekir).
- **Yükleme kuralları (`polls/images.py`):** Sadece JPG/PNG/WebP, en fazla **3 MB** (Vercel istek gövdesi sınırı ~4,5 MB), en fazla 40 milyon piksel. Dosya uzantıya/başlığa değil **içeriğe göre** Pillow ile çözülür; bozuk, sahte (metin/SVG/HTML), GIF/BMP dosyalar reddedilir. Sadece giriş yapmış üyeler yükler.
- **Gizlilik ve güvenlik:** Her fotoğraf yeniden kodlanır: **EXIF/konum bilgisi silinir**, telefon dönüşü uygulanır, saydamlık beyaza düzleştirilir, en uzun kenar 1200px'e (gerekirse 1000/800) küçültülür ve **WebP**'ye çevrilir (≤ ~500 KB). Sunucu her zaman `image/webp` + `nosniff` döner; yüklenen dosyanın kendisi asla sunulmaz. Yüklemeler diske yazılmaz (sadece bellek).
- **Moderasyon (asgari):** Formda "Uygunsuz içerik yasaktır" uyarısı. Admin panelinde Anketler listesinden seçili anketler için **"fotoğrafı kaldır"** eylemi vardır. CDN önbelleği kısa tutulur (en fazla ~1 saat). "Bildir" butonu sonraki aşamaya kalmıştır.
- **Arayüz:** Formda önizlemeli, "Fotoğrafı kaldır" butonlu alan; kartta ve detayda 16:9 sabit oranlı görsel (kırpılır; detayda tıklayınca tamamı açılır), `loading="lazy"`, alt metni sorunun kendisi. Anket silinince fotoğraf da silinir.

---

## 11. Prototip Kapsamı Dışında (şimdilik YAPMA)

Aşağıdakiler daha sonraki aşamalar için not edilmiştir, bu fazlarda **eklenmeyecek**:

- Takip, arkadaşlık, bildirim sistemi
- Yorum, beğeni, anket paylaşma/kategori/etiket/arama
- Normal anketlere süre koyma veya anketi elle kapatma (süre sadece Acil Karar'da var)
- Oy değiştirme
- E-posta doğrulama, parola sıfırlama
- Sosyal medya ile giriş
- Profil sayfaları, avatar
- Raporlama/moderasyon, spam koruması, rate limiting
- Admin dışı yönetim paneli (Django admin yeterli)
- Anket özetini gerçek bir yapay zeka modeline (LLM) yorumlatmak (şimdilik kural tabanlı özet var; sonraki aşama: API anahtarı, maliyet sınırı, önbellek ve kullanıcı metni güvenliği gerekir)

---

## 12. Claude Code İçin Çalışma Kuralları

1. Her seferinde yalnızca **istenen fazı** uygula. Faz bitince özet ver ve dur.
2. Basit tut: bu bir prototip. Yeni bağımlılık eklemeden önce gerekçeni kısaca söyle.
3. Kod ve yorumlar İngilizce olabilir; **kullanıcıya görünen tüm metinler Türkçe** olmalı.
4. Türkçe değişken adı kullanma; model, alan ve fonksiyon adları İngilizce.
5. Gizli bilgileri (parola, anahtar, bağlantı dizesi) koda veya git'e yazma.
6. Veritabanını etkileyen değişikliklerde (model/migration) ne yaptığını açıkla.
7. Yazdığın kod çalıştırılabilir olmalı; faz sonunda `manage.py check` ve (varsa) testleri çalıştır.
8. Belirsiz bir durumda varsayım yapıp ilerle ama varsayımı özetinde açıkça belirt.

---

## 13. Başlangıç Prompt'ları (kopyala-yapıştır)

> Dosya `docs/CLAUDE.md` konumunda durduğu için aşağıdaki prompt'larda geçen "CLAUDE.md dosyasını oku" ifadesini **"docs/CLAUDE.md dosyasını oku"** olarak kullan.

**Faz 0:**
```
docs/CLAUDE.md dosyasını oku. Sadece Faz 0'ı uygula: proje iskeleti, bağımlılıklar, ayarlar ve Supabase bağlantısı. Başka faza geçme. Bitince ne yaptığını ve benim yapmam gereken adımları (Supabase bağlantı bilgisini .env'e koymak gibi) özetle.
```

**Faz 1:**
```
docs/CLAUDE.md dosyasını oku. Faz 0 tamam. Şimdi sadece Faz 1'i uygula: özel User modeli ve kayıt/giriş/çıkış. Bitince dur ve özetle.
```

**Faz 2:**
```
docs/CLAUDE.md dosyasını oku. Faz 1 tamam. Şimdi sadece Faz 2'yi uygula: anket oluşturma, listeleme ve detay sayfası. Bitince dur ve özetle.
```

**Faz 3:**
```
docs/CLAUDE.md dosyasını oku. Faz 2 tamam. Şimdi sadece Faz 3'ü uygula: oy verme ve sonuçlar. Bitince dur ve özetle.
```

**Faz 4:**
```
docs/CLAUDE.md dosyasını oku. Faz 3 tamam. Şimdi sadece Faz 4'ü uygula: arayüz cilası, Anketlerim sayfası, silme ve testler. Bitince dur ve özetle.
```

**Faz 5:**
```
docs/CLAUDE.md dosyasını oku. Faz 4 tamam. Şimdi sadece Faz 5'i uygula: Vercel'e yayın hazırlığı. Önce Vercel'in güncel Django dokümantasyonunu kontrol et. Gizli değerleri benim girmem gereken adımlar olarak listele.
```
