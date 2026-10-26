from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Veritabanı bağlantısını dener (SELECT 1). Parolayı yazdırmaz."

    def handle(self, *args, **options):
        settings_dict = connection.settings_dict
        host = settings_dict.get("HOST") or "(yerel)"
        port = settings_dict.get("PORT") or "-"
        user = settings_dict.get("USER") or "-"  # contains the Supabase project ref, not a secret
        self.stdout.write(f"Bağlanılıyor: {connection.vendor} @ {host}:{port} (kullanıcı: {user})")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        if row and row[0] == 1:
            self.stdout.write(self.style.SUCCESS("Bağlantı başarılı."))
        else:
            self.stderr.write(self.style.ERROR("Beklenmeyen yanıt: %r" % (row,)))
