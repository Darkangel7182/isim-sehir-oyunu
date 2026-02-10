import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime # <-- Bunu importların arasına ekle

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
bekleyen_oyuncular = []
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

# --- VERİ YÜKLEME MOTORU ---
KELIME_HAVUZU = {
    "İsim": set(), "Şehir": set(), "Hayvan": set(), "Bitki": set(),
    "Ülke": set(), "Ünlü": set(), "Eşya": set(), "Yemek": set()
}

def verileri_yukle():
    dosya_eslesmeleri = {
        "İsim": "isim.txt", "Şehir": "sehir.txt", "Hayvan": "hayvan.txt",
        "Bitki": "bitki.txt", "Ülke": "ulke.txt", "Ünlü": "unlu.txt",
        "Eşya": "esya.txt", "Yemek": "yemek.txt"
    }
    
    base_path = os.path.join(os.path.dirname(__file__), 'data')
    
    if not os.path.exists(base_path):
        try:
            os.makedirs(base_path)
            print("UYARI: 'data' klasörü bulunamadı, oluşturuldu.")
        except:
            pass

    for kategori, dosya_adi in dosya_eslesmeleri.items():
        dosya_yolu = os.path.join(base_path, dosya_adi)
        if os.path.exists(dosya_yolu):
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                icerik = set(line.strip().upper() for line in f if line.strip())
                KELIME_HAVUZU[kategori] = icerik
            print(f"{kategori} yüklendi: {len(KELIME_HAVUZU[kategori])} kelime.")
        else:
            print(f"UYARI: {dosya_adi} bulunamadı! Bu kategori için sadece harf kontrolü yapılacak.")

verileri_yukle()

# --- DOĞRULAMA FONKSİYONU ---
def kelime_gecerli_mi(kategori, kelime, harf):
    kelime = kelime.strip().upper()
    if not kelime or not kelime.startswith(harf):
        return False
    
    if len(KELIME_HAVUZU.get(kategori, [])) == 0:
        return True 
        
    return kelime in KELIME_HAVUZU.get(kategori, set())

# --- SOCKET EVENTLERİ (FLUTTER İLE TAM UYUMLU) ---

@socketio.on('oda_olustur')  # Flutter: oda_olustur gönderiyor
def handle_create(data):
    # Veri anahtarlarını Flutter'a göre alıyoruz
    room_name = data.get('oda') or data.get('roomName')
    password = data.get('sifre') or data.get('password')
    nick = data.get('nickname', 'Anonim')

    odalar[room_name] = {
        'password': password, 
        'host': request.sid, 
        'letter': '',
        'categories': ["İsim", "Şehir", "Hayvan", "Bitki", "Eşya"],
        'players': {request.sid: nick}, 
        'answers': {}, 
        'scored': False
    }
    join_room(room_name)
    
    # Host'a bildirim (oda_katildi)
    emit('oda_katildi', {
        'oda': room_name, 
        'is_host': True, 
        'kategoriler': odalar[room_name]['categories']
    })
    
    # Oyuncu listesini güncelle
    player_list = list(odalar[room_name]['players'].values())
    emit('oyuncular_guncellendi', {'oyuncular': player_list})

@socketio.on('oda_katil') # Flutter: oda_katil gönderiyor
def handle_join(data):
    room_name = data.get('oda') or data.get('roomName')
    password = data.get('sifre') or data.get('password')
    nick = data.get('nickname', 'Misafir')

    if room_name in odalar and odalar[room_name]['password'] == password:
        join_room(room_name)
        odalar[room_name]['players'][request.sid] = nick
        
        player_list = list(odalar[room_name]['players'].values())
        
        # Katılan kişiye bildirim
        emit('oda_katildi', {
            'oda': room_name, 
            'is_host': False, 
            'kategoriler': odalar[room_name]['categories']
        })
        
        # Kategorileri güncelle
        emit('kategorileri_guncelle', {'kategoriler': odalar[room_name]['categories']}, room=room_name)
        
        # Tüm odaya oyuncu listesi
        emit('oyuncular_guncellendi', {'oyuncular': player_list}, room=room_name)
    else:
        emit('hata', {'mesaj': 'Hatalı giriş veya oda yok!'})

@socketio.on('hemen_oyna') # Flutter: hemen_oyna gönderiyor
def handle_matchmaking(data):
    nick = data.get('nickname', 'Oyuncu')
    bekleyen_oyuncular.append({'sid': request.sid, 'nick': nick})
    emit('eslesme_bekleniyor', {'mesaj': 'Rakip aranıyor...'})

    if len(bekleyen_oyuncular) >= 2:
        p1 = bekleyen_oyuncular.pop(0)
        p2 = bekleyen_oyuncular.pop(0)
        match_room = f"match_{uuid.uuid4().hex[:8]}"
        
        all_cats = ["İsim", "Şehir", "Hayvan", "Bitki", "Ülke", "Eşya", "Yemek", "Ünlü"]
        selected_cats = random.sample(all_cats, 5)
        
        odalar[match_room] = {
            'password': None, 
            'host': p1['sid'], 
            'letter': random.choice(HARFLER),
            'categories': selected_cats,
            'players': {p1['sid']: p1['nick'], p2['sid']: p2['nick']},
            'answers': {}, 
            'scored': False
        }
        
        for p in [p1, p2]: 
            join_room(match_room, sid=p['sid'])
            
        emit('eslesme_tamam', {
            'oda': match_room, 
            'harf': odalar[match_room]['letter'], 
            'kategoriler': selected_cats
        }, room=match_room)

@socketio.on('iptal_et')
def handle_cancel():
    global bekleyen_oyuncular
    bekleyen_oyuncular = [p for p in bekleyen_oyuncular if p['sid'] != request.sid]

@socketio.on('oyunu_baslat') # Flutter: oyunu_baslat
def handle_start(data):
    room_name = data.get('oda')
    if room_name in odalar and odalar[room_name]['host'] == request.sid:
        odalar[room_name].update({
            'letter': random.choice(HARFLER), 
            'answers': {}, 
            'scored': False
        })
        
        # Flutter 'yeni_oyun_basladi' eventini ve 'harf' keyini bekliyor
        emit('yeni_oyun_basladi', {
            'harf': odalar[room_name]['letter'], 
            'kategoriler': odalar[room_name]['categories']
        }, room=room_name)

@socketio.on('cevaplari_gonder') # Flutter: cevaplari_gonder
def handle_answers(data):
    room_name = data.get('oda')
    # Flutter 'cevaplar' keyini gönderiyor
    if room_name in odalar:
        odalar[room_name]['answers'][request.sid] = data['cevaplar']

@socketio.on('oyunu_bitir') # Flutter: oyunu_bitir
def handle_finish(data):
    room_name = data.get('oda')
    # Flutter 'geri_sayim_baslat' eventini ve 'sure' keyini bekliyor
    emit('geri_sayim_baslat', {'sure': 10}, room=room_name)
    socketio.sleep(12) 
    
    if room_name in odalar and not odalar[room_name]['scored']:
        puanla(room_name)
        odalar[room_name]['scored'] = True

@socketio.on('kategori_degistir') # Flutter: kategori_degistir
def handle_category_change(data):
    room_name = data.get('oda')
    if room_name in odalar and odalar[room_name]['host'] == request.sid:
        odalar[room_name]['categories'] = data['kategoriler']
        emit('kategorileri_guncelle', {'kategoriler': odalar[room_name]['categories']}, room=room_name)

@socketio.on('disconnect')
def handle_disconnect():
    # Burada oyuncu çıkarsa listeyi güncellemek iyi olur ama şimdilik kalsın
    pass

def puanla(room_name):
    results = {}
    room_data = odalar[room_name]
    cats, letter = room_data['categories'], room_data['letter']
    answers_pool, players = room_data['answers'], room_data['players']
    
    for sid, player_answers in answers_pool.items():
        total_score = 0
        details = {}
        
        for cat in cats:
            word = player_answers.get(cat, "").strip().upper()
            
            if kelime_gecerli_mi(cat, word, letter):
                others_words = [
                    v.get(cat, "").strip().upper() 
                    for s, v in answers_pool.items() 
                    if s != sid
                ]
                score = 5 if word in others_words else 10
            else:
                score = 0
            
            total_score += score
            # Flutter 'detay', 'kelime', 'puan' bekliyor
            details[cat] = {"kelime": word, "puan": score}
            
        # Flutter 'toplam' ve 'detay' keylerini bekliyor
        results[sid] = {
            "toplam": total_score, 
            "detay": details, 
            "nickname": players.get(sid, "Bilinmiyor")
        }
        
    # Flutter 'puan_durumu' eventini bekliyor
    emit('puan_durumu', results, room=room_name)

# --- SOHBET EVENTİ ---
@socketio.on('sohbet_gonder')
def handle_chat(data):
    room_name = data.get('roomName')
    message = data.get('message')
    sender = data.get('sender')
    
    if room_name:
        # Şu anki saati al (Örn: 14:30)
        zaman = datetime.now().strftime("%H:%M")
        
        # Odaya yay (broadcast)
        emit('sohbet_al', {
            'sender': sender,
            'message': message,
            'time': zaman
        }, room=room_name)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

