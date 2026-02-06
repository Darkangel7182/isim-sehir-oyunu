import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
bekleyen_oyuncular = [] # Matchmaking sırası
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

@socketio.on('oda_olustur')
def handle_create(data):
    oda, sifre, nick = data['oda'], data['sifre'], data.get('nickname', 'Anonim')
    odalar[oda] = {
        'sifre': sifre, 'host': request.sid, 'harf': '',
        'kategoriler': ["İsim", "Şehir", "Hayvan"],
        'oyuncular': {request.sid: nick}, 'cevaplar': {}, 'puanlandi': False
    }
    join_room(oda)
    emit('oda_katildi', {'oda': oda, 'is_host': True})

@socketio.on('oda_katil')
def handle_join(data):
    oda, sifre, nick = data['oda'], data['sifre'], data.get('nickname', 'Misafir')
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        odalar[oda]['oyuncular'][request.sid] = nick
        emit('oda_katildi', {'oda': oda, 'is_host': False})
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('hemen_oyna')
def handle_matchmaking(data):
    nick = data.get('nickname', 'Oyuncu')
    # Oyuncuyu sıraya ekle
    bekleyen_oyuncular.append({'sid': request.sid, 'nick': nick})
    emit('eslesme_bekleniyor', {'mesaj': 'Rakip aranıyor...'})

    if len(bekleyen_oyuncular) >= 2:
        # İki oyuncuyu sıradan çıkar
        p1 = bekleyen_oyuncular.pop(0)
        p2 = bekleyen_oyuncular.pop(0)
        
        # Rastgele bir oda ID'si oluştur
        match_room = f"match_{uuid.uuid4().hex[:8]}"
        odalar[match_room] = {
            'sifre': None, 'host': p1['sid'], 'harf': random.choice(HARFLER),
            'kategoriler': ["İsim", "Şehir", "Hayvan", "Bitki"],
            'oyuncular': {p1['sid']: p1['nick'], p2['sid']: p2['nick']},
            'cevaplar': {}, 'puanlandi': False
        }
        
        # Her iki oyuncuyu odaya al ve başlat
        for p in [p1, p2]:
            join_room(match_room, sid=p['sid'])
        
        emit('eslesme_tamam', {
            'oda': match_room, 
            'harf': odalar[match_room]['harf'], 
            'kategoriler': odalar[match_room]['kategoriler']
        }, room=match_room)

@socketio.on('oyunu_baslat')
def handle_start(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda].update({'harf': random.choice(HARFLER), 'cevaplar': {}, 'puanlandi': False})
        emit('yeni_oyun_basladi', {'harf': odalar[oda]['harf'], 'kategoriler': odalar[oda]['kategoriler']}, room=oda)

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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
