import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
bekleyen_oyuncular = []
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

# --- VERİ YÜKLEME MOTORU ---
# Kelimeleri hafızada tutacağımız sözlük
KELIME_HAVUZU = {
    "İsim": set(), "Şehir": set(), "Hayvan": set(), "Bitki": set(),
    "Ülke": set(), "Ünlü": set(), "Eşya": set(), "Yemek": set()
}

def verileri_yukle():
    """data klasöründeki txt dosyalarını okur ve kümeye ekler."""
    dosya_eslesmeleri = {
        "İsim": "isim.txt", "Şehir": "sehir.txt", "Hayvan": "hayvan.txt",
        "Bitki": "bitki.txt", "Ülke": "ulke.txt", "Ünlü": "unlu.txt",
        "Eşya": "esya.txt", "Yemek": "yemek.txt"
    }
    
    base_path = os.path.join(os.path.dirname(__file__), 'data')
    
    # Klasör yoksa hata vermemesi için oluştur (Boş çalışırsa çökmesin)
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        print("UYARI: 'data' klasörü bulunamadı, oluşturuldu. Lütfen içine txt dosyalarını ekleyin.")

    for kategori, dosya_adi in dosya_eslesmeleri.items():
        dosya_yolu = os.path.join(base_path, dosya_adi)
        if os.path.exists(dosya_yolu):
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                # Satır satır oku, boşlukları temizle, büyük harfe çevir ve ekle
                icerik = set(line.strip().upper() for line in f if line.strip())
                KELIME_HAVUZU[kategori] = icerik
            print(f"{kategori} yüklendi: {len(KELIME_HAVUZU[kategori])} kelime.")
        else:
            print(f"UYARI: {dosya_adi} bulunamadı! Bu kategori için sadece harf kontrolü yapılacak.")

# Sunucu başlarken verileri yükle
verileri_yukle()

# --- DOĞRULAMA FONKSİYONU ---
def kelime_gecerli_mi(kategori, kelime, harf):
    kelime = kelime.strip().upper()
    
    # 1. Boş mu ve Harf Doğru mu?
    if not kelime or not kelime.startswith(harf):
        return False
    
    # 2. Kelime Havuzunda Var mı?
    # Eğer o kategori için listemiz boşsa (dosya yoksa), oyuncuyu mağdur etmemek için kabul et.
    if len(KELIME_HAVUZU.get(kategori, [])) == 0:
        return True 
        
    return kelime in KELIME_HAVUZU.get(kategori, set())

# --- STANDART SOCKET EVENTLERİ ---

@socketio.on('oda_olustur')
def handle_create(data):
    oda, sifre, nick = data['oda'], data['sifre'], data.get('nickname', 'Anonim')
    odalar[oda] = {
        'sifre': sifre, 'host': request.sid, 'harf': '',
        'kategoriler': ["İsim", "Şehir", "Hayvan", "Bitki", "Eşya"],
        'oyuncular': {request.sid: nick}, 'cevaplar': {}, 'puanlandi': False
    }
    join_room(oda)
    
    # KENDİNE LİSTEYİ GÖNDER (HOST KENDİNİ GÖRSÜN)
    oyuncu_listesi = list(odalar[oda]['oyuncular'].values())
    emit('oda_katildi', {'oda': oda, 'is_host': True, 'kategoriler': odalar[oda]['kategoriler']})
    emit('oyuncular_guncellendi', {'oyuncular': oyuncu_listesi}) # <-- YENİ EKLENDİ

@socketio.on('oda_katil')
def handle_join(data):
    oda, sifre, nick = data['oda'], data['sifre'], data.get('nickname', 'Misafir')
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        odalar[oda]['oyuncular'][request.sid] = nick
        
        # HERKESE GÜNCEL LİSTEYİ GÖNDER
        oyuncu_listesi = list(odalar[oda]['oyuncular'].values())
        
        emit('oda_katildi', {'oda': oda, 'is_host': False, 'kategoriler': odalar[oda]['kategoriler']})
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)
        emit('oyuncular_guncellendi', {'oyuncular': oyuncu_listesi}, room=oda) # <-- YENİ EKLENDİ (Tüm odaya)
    else:
        emit('hata', {'mesaj': 'Hatalı giriş!'})

@socketio.on('hemen_oyna')
def handle_matchmaking(data):
    nick = data.get('nickname', 'Oyuncu')
    bekleyen_oyuncular.append({'sid': request.sid, 'nick': nick})
    emit('eslesme_bekleniyor', {'mesaj': 'Rakip aranıyor...'})

    if len(bekleyen_oyuncular) >= 2:
        p1 = bekleyen_oyuncular.pop(0)
        p2 = bekleyen_oyuncular.pop(0)
        match_room = f"match_{uuid.uuid4().hex[:8]}"
        # Matchmaking için tüm kategorilerden rastgele 5 tane seçebiliriz veya sabit tutabiliriz
        tum_kats = ["İsim", "Şehir", "Hayvan", "Bitki", "Ülke", "Eşya", "Yemek", "Ünlü"]
        secilen_kats = random.sample(tum_kats, 5) # Her maç farklı 5 kategori!
        
        odalar[match_room] = {
            'sifre': None, 'host': p1['sid'], 'harf': random.choice(HARFLER),
            'kategoriler': secilen_kats,
            'oyuncular': {p1['sid']: p1['nick'], p2['sid']: p2['nick']},
            'cevaplar': {}, 'puanlandi': False
        }
        for p in [p1, p2]: join_room(match_room, sid=p['sid'])
        emit('eslesme_tamam', {'oda': match_room, 'harf': odalar[match_room]['harf'], 'kategoriler': secilen_kats}, room=match_room)

@socketio.on('iptal_et')
def handle_cancel():
    global bekleyen_oyuncular
    bekleyen_oyuncular = [p for p in bekleyen_oyuncular if p['sid'] != request.sid]

@socketio.on('oyunu_baslat')
def handle_start(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda].update({'harf': random.choice(HARFLER), 'cevaplar': {}, 'puanlandi': False})
        emit('yeni_oyun_basladi', {'harf': odalar[oda]['harf'], 'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oda = data['oda']
    if oda in odalar:
        odalar[oda]['cevaplar'][request.sid] = data['cevaplar']

@socketio.on('oyunu_bitir')
def handle_finish(data):
    oda = data['oda']
    emit('geri_sayim_baslat', {'sure': 10}, room=oda)
    socketio.sleep(12)
    if oda in odalar and not odalar[oda]['puanlandi']:
        puanla(oda)
        odalar[oda]['puanlandi'] = True

@socketio.on('kategori_degistir')
def handle_category_change(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['kategoriler'] = data['kategoriler']
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)

def puanla(oda):
    sonuclar = {}
    kats, harf = odalar[oda]['kategoriler'], odalar[oda]['harf']
    havuz, isimler = odalar[oda]['cevaplar'], odalar[oda]['oyuncular']
    
    for sid, cevaplar in havuz.items():
        toplam, detay = 0, {}
        for k in kats:
            kelime = cevaplar.get(k, "").strip().upper()
            
            # Güncellenmiş Doğrulama Sistemi
            if kelime_gecerli_mi(k, kelime, harf):
                digerleri = [v.get(k, "").strip().upper() for s, v in havuz.items() if s != sid]
                puan = 5 if kelime in digerleri else 10
            else:
                puan = 0 # Listede yoksa 0 puan
            
            toplam += puan
            detay[k] = {"kelime": kelime, "puan": puan}
        sonuclar[sid] = {"toplam": toplam, "detay": detay, "nickname": isimler.get(sid, "Bilinmiyor")}
    emit('puan_durumu', sonuclar, room=oda)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

