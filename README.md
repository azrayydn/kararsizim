<p align="center">
  <img src="static/img/logo.svg" alt="kararsızım logosu" width="72" height="72">
</p>

<h1 align="center">kararsızım</h1>

<p align="center">
  Kararsız kaldığın şeyi sor, millet karar versin.<br>
  <sub>Django · PostgreSQL (Supabase) · Vercel</sub>
</p>

<p align="center">
  <a href="https://kararsizim-live.vercel.app">Canlı site</a>
</p>

---

**Kararsızım**, insanların karar veremediği konularda diğer kullanıcılara danışabildiği bir anket sitesidir.
"Bugün sinemaya mı gitsem, restorana mı?" gibi bir soru yazarsın, 2 ile 5 arasında seçenek eklersin, diğer üyeler oylar.
Anketleri herkes görebilir, oy vermek ve anket açmak için üye olmak gerekir. Takip mekanizması yoktur: herkes her anketi görür.

> Bu bir **prototiptir**. Önce çalışan, sade bir sürüm çıkarmak hedeflendi; gelişmiş özellikler adım adım eklenecek.

## İçindekiler

- [Özellikler](#özellikler)
- [Acil Karar ve rozetler](#acil-karar-ve-rozetler)
- [Teknolojiler](#teknolojiler)
- [Yerelde çalıştırma](#yerelde-çalıştırma)
- [Ortam değişkenleri](#ortam-değişkenleri)
- [Testler](#testler)
- [Proje yapısı](#proje-yapısı)
- [Canlıya alma (Vercel + Supabase)](#canlıya-alma-vercel--supabase)
- [Güvenlik ve gizlilik](#güvenlik-ve-gizlilik)
- [Bilinen sınırlar ve yol haritası](#bilinen-sınırlar-ve-yol-haritası)

## Özellikler

| Alan | Neler var |
|---|---|
| **Anketler** | 2-5 seçenekli anketler, yeniden eskiye sıralı akış, sayfalama, anket sayfası, kendi anketini silme ("Anketlerim") |
| **Oylama** | Giriş yapan herkes her ankete **bir kez** oy verir. Sonuçlar yüzde çubuklarıyla herkese açıktır |
| **Üyelik** | E-posta + parola ile giriş, herkese görünen **kullanıcı adı**. E-posta hiçbir sayfada gösterilmez |
| **Anket özeti kartı** | Sonuçları yorumlayan küçük, samimi bir kart ("Kıran kırana!", "Net karar"...). Metinler kurallarla üretilir, yapay zeka değildir |
| **Acil Karar** | 5 dakikalık anket: süre dolana kadar sonuç gizli, süre dolunca sonuç **kilitlenir** |
| **Rozetler** | Topluluğun seçtiği tarafa oy verenlere rozet (Karar Çırağı, Karar Verici, Master Karar Verici, Guru) |
| **Fotoğraf** | Ankete isteğe bağlı bir fotoğraf eklenebilir (otomatik küçültülür, konum bilgisi silinir) |
| **Arayüz** | Mobil öncelikli, açık adaçayı teması, geniş ekranda yan paneller (Nasıl çalışır, Popüler anketler), toast bildirimleri |
| **Yönetim** | Django admin paneli; anketlerin fotoğrafını kaldırma eylemi |

### Sayfalar

| Adres | Açıklama | Erişim |
|---|---|---|
| `/` | Anket akışı | Herkes |
| `/anket/<id>/` | Anket, sonuçlar, özet kartı | Herkes |
| `/anket/yeni/` | Anket oluşturma | Üyeler |
| `/ben/` | Anketlerim ve rozetim | Üyeler |
| `/kayit/`, `/giris/` | Kayıt ve giriş | Herkes |
| `/admin/` | Yönetim paneli | Yöneticiler |

## Acil Karar ve rozetler

**Acil Karar:** Anket açarken "Acil Karar yap" işaretlenirse anket 5 dakika açık kalır.

- Süre dolana kadar **kimse sonucu göremez**: yüzdeler, oy sayıları ve çubuklar sayfaya hiç yazılmaz. Sadece "N kişi oy verdi" görünür.
- Süre kontrolü **sunucuda** yapılır. Sayfadaki geri sayım sadece görüntüdür; süre bittikten sonra gelen oy reddedilir.
- Süre dolunca sayaç sıfırlanır, sonuçlar açılır ve kilitlenir.

**Rozetler:** Süresi dolmuş, en az **5 oy** almış ve **net bir kazananı olan** Acil Karar anketlerinde, kazanan seçeneğe oy veren kişi "isabet" sayar. Kendi anketine verilen oy ve normal anketler sayılmaz.

| Rozet | Koşul |
|---|---|
| Karar Çırağı | en az 3 sayılan oy |
| Karar Verici | en az 8 oy ve %55 isabet |
| Master Karar Verici | en az 20 oy ve %65 isabet |
| Guru | en az 40 oy ve %75 isabet |

Sonuçlar süre dolana kadar gizli olduğu için "önde olana oy verip rozet toplamak" mümkün değildir. Herkese sadece rozet adı görünür; sayılar ve oran yalnızca kişinin kendi sayfasındadır.

## Teknolojiler

- **Python 3.12+** ve **Django 6.1**
- **PostgreSQL**, [Supabase](https://supabase.com) üzerinde (yerelde SQLite ile de çalışır)
- **Vercel** üzerinde barındırma
- Ön yüz: Django şablonları, saf HTML, CSS ve JavaScript (ayrı bir framework yok)
- **WhiteNoise** (statik dosyalar), **Pillow** (fotoğraf işleme), **psycopg 3**, `dj-database-url`, `python-dotenv`

## Yerelde çalıştırma

Gereken: **Python 3.12 veya üstü**.

```bash
# 1. Sanal ortam
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 2. Bağımlılıklar
pip install -r requirements.txt

# 3. Ayar dosyası
cp .env.example .env        # Windows: copy .env.example .env
```

`.env` dosyasını aç ve doldur. En kolay başlangıç için veritabanı olarak SQLite kullanabilirsin:

```ini
SECRET_KEY=buraya-uzun-rastgele-bir-yazi
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

Rastgele bir `SECRET_KEY` üretmek için:
```bash
python -c "import secrets; print(secrets.token_urlsafe(60))"
```

Supabase kullanmak istersen `DATABASE_URL` yerine Supabase projenin **Transaction pooler** adresini yaz ([Canlıya alma](#canlıya-alma-vercel--supabase) bölümüne bak).

```bash
# 4. Tabloları oluştur ve yönetici hesabı aç
python manage.py migrate
python manage.py createsuperuser

# 5. Çalıştır
python manage.py runserver
```

Tarayıcıda <http://127.0.0.1:8000> adresini aç. Veritabanı bağlantısını denemek için: `python manage.py check_db`.

## Ortam değişkenleri

Değerler `.env` dosyasından (yerelde) veya Vercel panelinden (canlıda) okunur. `.env` dosyası **asla** git'e eklenmez.

| Değişken | Açıklama | Örnek |
|---|---|---|
| `SECRET_KEY` | Django gizli anahtarı. Canlıda yerelden **farklı** olmalı | uzun rastgele yazı |
| `DEBUG` | Canlıda **`False`** olmalı | `True` / `False` |
| `ALLOWED_HOSTS` | Virgülle ayrılmış site adresleri | `localhost,127.0.0.1,.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | Güvenilen kaynaklar (`https://` ile) | `https://*.vercel.app` |
| `DATABASE_URL` | Veritabanı adresi | `sqlite:///db.sqlite3` veya Supabase adresi |
| `MIGRATION_DATABASE_URL` | Sadece başka bir veritabanına migration için (aşağıya bak) | Supabase session pooler adresi |

Başka bir alan adı eklersen onu `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` değişkenlerine de eklemelisin.

## Testler

```bash
python manage.py test --settings=config.settings_test
```

150'den fazla otomatik test vardır (üyelik, oylama, Acil Karar, rozetler, fotoğraf işleme, yetkiler, e-postanın gizliliği...). Testler **bellekte SQLite** kullanır, Supabase'e bağlanmaz.

## Proje yapısı

```
.
├── accounts/        Özel kullanıcı modeli, kayıt / giriş / çıkış
├── polls/           Anketler, oylar, Acil Karar, rozetler, özet kartı, fotoğraflar
│   ├── badges.py    Rozet hesaplama ve anketlerin kesinleşmesi
│   ├── insights.py  Sonuç yorumları (kural tabanlı)
│   └── images.py    Fotoğraf doğrulama, küçültme, WebP'ye çevirme
├── config/          Django ayarları (settings, settings_test, settings_migrate)
├── templates/       HTML şablonları
├── static/          CSS, JavaScript, logo
├── docs/
│   ├── CLAUDE.md          Ayrıntılı proje planı ve kararlar
│   └── supabase_rls.sql   Supabase güvenlik betiği (aşağıya bak)
├── manage.py
├── requirements.txt
└── .python-version
```

Projenin neden böyle tasarlandığını ve alınan kararları `docs/CLAUDE.md` dosyasında bulabilirsin.

## Canlıya alma (Vercel + Supabase)

Vercel, Django projesini `manage.py` dosyasından **kendisi tanır**; statik dosyaları build sırasında kendisi toplar. Ayrı bir build ayarı gerekmez.

### 1. Canlı veritabanı (Supabase)

Geliştirme ve canlı için **iki ayrı Supabase projesi** kullanılması önerilir.

1. Canlı projenin **Session pooler** adresini al (port `5432`), parolayı yaz.
2. Adresi bilgisayarında **geçici** bir değişkene yaz (dosyaya yazma) ve **hangi projeye bağlandığını doğrula**:
   ```powershell
   $env:MIGRATION_DATABASE_URL = Read-Host "Adresi yapistir"
   python manage.py check_db --settings=config.settings_migrate
   ```
   Çıktıdaki `kullanıcı: postgres.XXXX` kodunun **canlı** projeye ait olduğundan emin ol. `MIGRATION_DATABASE_URL` tanımlı değilse bu ayar dosyası `DATABASE_URL`'e (geliştirme veritabanına) düşebilir; bu yüzden önce kontrol et.
3. Tabloları oluştur:
   ```powershell
   python manage.py migrate --settings=config.settings_migrate
   python manage.py createsuperuser --settings=config.settings_migrate
   Remove-Item Env:MIGRATION_DATABASE_URL
   ```
4. Supabase **SQL Editor**'de [`docs/supabase_rls.sql`](docs/supabase_rls.sql) dosyasını çalıştır. Bu, Django'nun tablolarının Supabase'in herkese açık erişim yolundan okunmasını engeller (Django bundan etkilenmez). **Yeni tablo ekleyen her migration'dan sonra tekrar çalıştır.**

### 2. Vercel

1. Depoyu Vercel'de **Add New → Project** ile içe aktar (Framework: Django).
2. **Deploy'dan önce** şu ortam değişkenlerini gir:

   | Değişken | Canlı değeri |
   |---|---|
   | `SECRET_KEY` | canlıya özel yeni anahtar |
   | `DEBUG` | `False` |
   | `DATABASE_URL` | canlı projenin **Transaction pooler** adresi (port `6543`) |
   | `ALLOWED_HOSTS` | `.vercel.app` |
   | `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` |

3. Deploy et. `main` dalına her `git push` yeni bir yayın başlatır.

Ortam değişkeni değiştirdikten sonra yeni değerin geçerli olması için **Redeploy** gerekir.

## Güvenlik ve gizlilik

- **E-posta adresleri** hiçbir sayfada, anket kartında veya yanıtta gösterilmez; yalnızca kullanıcı adı görünür.
- Parolalar Django'nun güvenli hash yöntemiyle saklanır; CSRF koruması açıktır; şablonlar kullanıcı metnini otomatik kaçışlar.
- Oy verme, silme ve çıkış yalnızca `POST` ile yapılır. Bir anketi yalnızca sahibi silebilir.
- Bir kullanıcı bir ankete **yalnızca bir kez** oy verebilir (veritabanı kuralıyla da korunur).
- **Acil Karar** sonuçları süre dolmadan sayfaya yazılmaz; süre kontrolü sunucudadır.
- **Fotoğraflar** yüklenirken yeniden kodlanır: konum (EXIF) bilgisi silinir, boyutu küçültülür, WebP'ye çevrilir. Sadece JPG/PNG/WebP ve en fazla 3 MB kabul edilir; sahte dosyalar reddedilir.
- Supabase tablolarında Row Level Security açıktır ([`docs/supabase_rls.sql`](docs/supabase_rls.sql)).
- Gizli bilgiler (`.env`, veritabanı parolaları, `SECRET_KEY`) depoda tutulmaz.

## Bilinen sınırlar ve yol haritası

**Bilinen sınırlar**

- E-posta doğrulaması ve parola sıfırlama yoktur; bu yüzden sahte hesaplarla oy veya rozet şişirilebilir.
- Hız sınırı (rate limit) ve "Bildir" butonu yoktur. Uygunsuz fotoğraflar şimdilik yalnızca admin panelinden kaldırılır.
- Fotoğraflar veritabanında saklanır (Supabase ücretsiz planında 500 MB sınırı vardır).
- Anket özeti kural tabanlıdır, bir yapay zeka modeli değildir.
- Bazı internet sağlayıcılarında `*.vercel.app` adreslerine erişimde sorun görülebilir (VPN ile açılabilir). Kalıcı çözüm olarak özel bir alan adı bağlanabilir.

**Yol haritası**

- [ ] E-posta doğrulaması ve parola sıfırlama
- [ ] "Bildir" butonu ve moderasyon
- [ ] Hız sınırı
- [ ] Fotoğrafları Supabase Storage'a taşıma, seçeneklere fotoğraf
- [ ] Gerçek bir yapay zeka modeliyle anket yorumu
- [ ] Özel alan adı
- [ ] Anketi açanlar için de rozetler

<!--
Ekran görüntüsü eklemek için:
1. Görüntüleri docs/screenshots/ klasörüne koy (ana-sayfa.png, anket.png, acil-karar.png gibi).
2. Aşağıdaki satırları açıp "Özellikler" bölümünün üstüne taşı:

![Ana sayfa](docs/screenshots/ana-sayfa.png)
![Anket sonuçları](docs/screenshots/anket.png)
-->
