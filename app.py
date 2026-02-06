import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
bekleyen_oyuncular = [] # Matchmaking havuzu
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

@socketio.on('oda_olustur')
def handle_create(data):
    oda = data['oda']
    sifre = data['sifre']
    nick = data.get('nickname', 'Anonim')
    # Varsayılan kategorilerle odayı kur
    odalar[oda] = {
        'sifre': sifre, 'host': request.sid, 'harf': '',
        'kategoriler': ["İsim", "Şehir", "Hayvan"],
        'oyuncular': {request.sid: nick}, 'cevaplar': {}, 'puanlandi': False
    }
    join_room(oda)
    # Lobiye girerken mevcut kategorileri de gönder
    emit('oda_katildi', {
        'oda': oda, 
        'is_host': True, 
        'kategoriler': odalar[oda]['kategoriler']
    })

@socketio.on('oda_katil')
def handle_join(data):
    oda = data['oda']
    sifre = data['sifre']
    nick = data.get('nickname', 'Misafir')
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        odalar[oda]['oyuncular'][request.sid] = nick
        # Katılan kişiye odanın GÜNCEL kategorilerini gönderiyoruz
        emit('oda_katildi', {
            'oda': oda, 
            'is_host': False, 
            'kategoriler': odalar[oda]['kategoriler']
        })
        # Odadaki diğer herkese de birinin katıldığını ve kategorileri bildir
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)
    else:
        emit('hata', {'mesaj': 'Oda adı veya şifre hatalı!'})

@socketio.on('kategori_degistir')
def handle_category_change(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['kategoriler'] = data['kategoriler']
        # Tüm odaya yeni kategorileri yayınla
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('hemen_oyna')
def handle_matchmaking(data):
    nick = data.get('nickname', 'Oyuncu')
    bekleyen_oyuncular.append({'sid': request.sid, 'nick': nick})
    emit('eslesme_bekleniyor', {'mesaj': 'Rakip aranıyor...'})

    if len(bekleyen_oyuncular) >= 2:
        p1 = bekleyen_oyuncular.pop(0)
        p2 = bekleyen_oyuncular.pop(0)
        match_room = f"match_{uuid.uuid4().hex[:8]}"
        
        # Hemen oyna için standart geniş kategori seti
        match_cats = ["İsim", "Şehir", "Hayvan", "Bitki"]
        odalar[match_room] = {
            'sifre': None, 'host': p1['sid'], 'harf': random.choice(HARFLER),
            'kategoriler': match_cats,
            'oyuncular': {p1['sid']: p1['nick'], p2['sid']: p2['nick']},
            'cevaplar': {}, 'puanlandi': False
        }
        for p in [p1, p2]: join_room(match_room, sid=p['sid'])
        # Eşleşme tamamlandığında kategorileri bas
        emit('eslesme_tamam', {
            'oda': match_room, 'harf': odalar[match_room]['harf'], 
            'kategoriler': match_cats
        }, room=match_room)

@socketio.on('oyunu_baslat')
def handle_start(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        # Odada seçili olan GÜNCEL kategorileri kullanarak başlat
        odalar[oda].update({'harf': random.choice(HARFLER), 'cevaplar': {}, 'puanlandi': False})
        emit('yeni_oyun_basladi', {
            'harf': odalar[oda]['harf'], 
            'kategoriler': odalar[oda]['kategoriler']
        }, room=oda)

@socketio.on('oyunu_bitir')
def handle_finish(data):
    oda = data['oda']
    emit('geri_sayim_baslat', {'sure': 10}, room=oda)
    socketio.sleep(12)
    if oda in odalar and not odalar[oda]['puanlandi']:
        puanla(oda)
        odalar[oda]['puanlandi'] = True

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oda = data['oda']
    if oda in odalar:
        odalar[oda]['cevaplar'][request.sid] = data['cevaplar']

def puanla(oda):
    sonuclar = {}
    kats, harf = odalar[oda]['kategoriler'], odalar[oda]['harf']
    havuz, isimler = odalar[oda]['cevaplar'], odalar[oda]['oyuncular']
    for sid, cevaplar in havuz.items():
        toplam, detay = 0, {}
        for k in kats:
            kelime = cevaplar.get(k, "").strip().upper()
            puan = 0
            if kelime and kelime.startswith(harf):
                digerleri = [v.get(k, "").strip().upper() for s, v in havuz.items() if s != sid]
                puan = 5 if kelime in digerleri else 10
            toplam += puan
            detay[k] = {"kelime": kelime, "puan": puan}
        sonuclar[sid] = {"toplam": toplam, "detay": detay, "nickname": isimler.get(sid, "Bilinmiyor")}
    emit('puan_durumu', sonuclar, room=oda)

# Mevcut bekleyen_oyuncular listesinin altına veya uygun bir yere ekle
@socketio.on('iptal_et')
def handle_cancel_matchmaking():
    global bekleyen_oyuncular
    # Oyuncunun sid'ini listeden filtreleyerek temizliyoruz
    bekleyen_oyuncular = [p for p in bekleyen_oyuncular if p['sid'] != request.sid]
    print(f"Oyuncu sıradan çıktı: {request.sid}")
    emit('eslesme_iptal', {'mesaj': 'Arama iptal edildi.'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
