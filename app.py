import os
import random
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fenerbahce1907'
socketio = SocketIO(app, cors_allowed_origins="*")

odalar = {}
HARFLER = "ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ"

@socketio.on('oda_olustur')
def handle_create(data):
    oda = data['oda']
    sifre = data['sifre']
    odalar[oda] = {
        'sifre': sifre,
        'host': request.sid,
        'kategoriler': ["İsim", "Şehir", "Hayvan"],
        'harf': '',
        'cevaplar': {},
        'puanlandi': False # Puanlamanın mükerrer olmasını engellemek için
    }
    join_room(oda)
    emit('oda_katildi', {'oda': oda, 'is_host': True})

@socketio.on('oda_katil')
def handle_join(data):
    oda = data['oda']
    sifre = data['sifre']
    if oda in odalar and odalar[oda]['sifre'] == sifre:
        join_room(oda)
        emit('oda_katildi', {'oda': oda, 'is_host': False})
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)
    else:
        emit('hata', {'mesaj': 'Oda adı veya şifre hatalı!'})

@socketio.on('kategori_degistir')
def handle_category_change(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['kategoriler'] = data['kategoriler']
        emit('kategorileri_guncelle', {'kategoriler': odalar[oda]['kategoriler']}, room=oda)

@socketio.on('oyunu_baslat')
def handle_start(data):
    oda = data['oda']
    if oda in odalar and odalar[oda]['host'] == request.sid:
        odalar[oda]['harf'] = random.choice(HARFLER)
        odalar[oda]['cevaplar'] = {}
        odalar[oda]['puanlandi'] = False
        emit('yeni_oyun_basladi', {
            'harf': odalar[oda]['harf'],
            'kategoriler': odalar[oda]['kategoriler']
        }, room=oda)

@socketio.on('oyunu_bitir')
def handle_finish(data):
    oda = data['oda']
    if oda in odalar:
        emit('geri_sayim_baslat', {'sure': 10}, room=oda)
        # 12 saniye bekle (10 saniye oyun + 2 saniye ağ gecikmesi)
        socketio.sleep(12) 
        if not odalar[oda]['puanlandi']:
            puanla(oda)
            odalar[oda]['puanlandi'] = True

@socketio.on('cevaplari_gonder')
def handle_answers(data):
    oda = data['oda']
    if oda in odalar:
        odalar[oda]['cevaplar'][request.sid] = data['cevaplar']
        # Burada artık puanla(oda) çağırmıyoruz, zamanlayıcıyı bekliyoruz

def puanla(oda):
    sonuclar = {}
    kategoriler = odalar[oda]['kategoriler']
    harf = odalar[oda]['harf']
    cevaplar_havuzu = odalar[oda]['cevaplar']
    
    for oyuncu, cevaplar in cevaplar_havuzu.items():
        toplam = 0
        detay = {}
        for kat in kategoriler:
            kelime = cevaplar.get(kat, "").strip().upper()
            puan = 0
            if kelime and kelime.startswith(harf):
                digerleri = [v.get(kat, "").strip().upper() for k, v in cevaplar_havuzu.items() if k != oyuncu]
                puan = 5 if kelime in digerleri else 10
            toplam += puan
            detay[kat] = {"kelime": kelime, "puan": puan}
        sonuclar[oyuncu] = {"toplam": toplam, "detay": detay}
    emit('puan_durumu', sonuclar, room=oda)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)