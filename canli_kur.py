"""Canlı (kararsizim-prod) Supabase veritabanını hazırlar.

Kullanım (proje klasöründe, sanal ortam açıkken):

    python canli_kur.py

Tek şey sorar: canlı veritabanının şifresi. Şifre yazarken ekranda görünmez, hiçbir dosyaya
yazılmaz ve komut satırına adres yazman gerekmez. Sırayla şunları yapar:

  1. Doğru projeye (canlı) bağlandığını doğrular, geliştirme veritabanına ASLA dokunmaz.
  2. Tabloları oluşturur (migrate).
  3. Tablolarda Row Level Security'yi açar (Supabase'in herkese açık erişimini kapatır).
  4. İstersen yönetici hesabını oluşturur.
"""
import os
import sys
from getpass import getpass
from urllib.parse import quote

# Canlı projenin bağlantı bilgileri. Bunlar gizli değildir (şifre değildir).
PROJECT_USER = "postgres.hcsspcfbvpnwvdmpekcd"
HOST = "aws-0-eu-west-1.pooler.supabase.com"
PORT = 5432  # session pooler
DBNAME = "postgres"
DEV_PROJECT_CODE = "mifgdzsugxfpqzvqxbbv"  # geliştirme projesi: buraya asla bağlanma

RLS_SQL = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
END $$;
"""
CHECK_SQL = "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"


def stop(message):
    print("\n" + message)
    sys.exit(1)


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("=== Kararsızım: canlı veritabanı kurulumu ===\n")
    print(f"Hedef: {PROJECT_USER} @ {HOST}:{PORT}")
    password = getpass("Canlı veritabanı şifresi (yazarken görünmez, yapıştırıp Enter'a bas): ").strip()
    if not password:
        stop("Şifre girilmedi, hiçbir şey yapılmadı.")

    url = f"postgresql://{PROJECT_USER}:{quote(password, safe='')}@{HOST}:{PORT}/{DBNAME}"
    # Hem normal hem migration adresi canlıya ayarlanır: geliştirme adresine düşme ihtimali yok.
    os.environ["DATABASE_URL"] = url
    os.environ["MIGRATION_DATABASE_URL"] = url
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_migrate"

    import django

    django.setup()
    from django.core.management import call_command
    from django.db import OperationalError, connection

    settings_dict = connection.settings_dict
    if DEV_PROJECT_CODE in (settings_dict.get("USER") or "") or settings_dict.get("USER") != PROJECT_USER:
        stop("Güvenlik durdurması: bağlanılacak veritabanı canlı proje değil. Hiçbir şey yapılmadı.")

    print("\n1/4 Bağlantı deneniyor...")
    try:
        connection.ensure_connection()
    except OperationalError as error:
        text = str(error)
        if "password authentication failed" in text:
            stop(
                "Şifre kabul edilmedi. Supabase'de kararsizim-prod projesinde (Project Settings > "
                "Database > Reset database password) kaydettiğin şifreyle, buraya yazdığın şifre "
                "birebir aynı olmalı. Şifreyi yeniden belirleyip tekrar dene."
            )
        stop("Bağlanılamadı. Hata (son satır): " + text.strip().splitlines()[-1])
    print("    Bağlantı başarılı (canlı proje).")

    print("\n2/4 Tablolar oluşturuluyor (migrate)...")
    call_command("migrate", verbosity=1, interactive=False)

    print("\n3/4 Güvenlik (Row Level Security) açılıyor...")
    with connection.cursor() as cursor:
        cursor.execute(RLS_SQL)
        cursor.execute(CHECK_SQL)
        rows = cursor.fetchall()
    for table, enabled in rows:
        print(f"    {'açık ' if enabled else 'KAPALI'}  {table}")
    if not rows or not all(enabled for _, enabled in rows):
        stop("Bazı tablolarda güvenlik açılamadı. Bana yukarıdaki listeyi gönder.")
    print(f"    {len(rows)} tablonun hepsinde açık.")

    print("\n4/4 Yönetici hesabı")
    from django.contrib.auth import get_user_model

    if get_user_model().objects.filter(is_superuser=True).exists():
        print("    Canlıda zaten bir yönetici hesabı var, atlandı.")
    else:
        answer = input("    Şimdi yönetici hesabı oluşturulsun mu? (e/h): ").strip().lower()
        if answer in ("e", "evet", "y"):
            call_command("createsuperuser")
        else:
            print("    Atlandı. Sonra istersen bu dosyayı yeniden çalıştırabilirsin.")

    print("\nTamam! Canlı veritabanı hazır. Şifre hiçbir yere kaydedilmedi.")
    print("Sıradaki adım: Vercel'de DATABASE_URL değişkenini yeni şifreyle güncelle.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nİptal edildi.")
