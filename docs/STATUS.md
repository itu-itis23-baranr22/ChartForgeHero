# Proje durumu

B3 devam ediyor, alt adımlara bölündü ve her birinin sonunda onay bekleniyor. Şartname ve alınan kararlar `docs/SPEC.md` dosyasında.

## Şu anki adım

**B3.0 (Danza tempo haritası) bitti ve onaylandı. Sırada B3.1 (gitarsız build + bas Expert), sonra B3.2 (bas Hard/Medium/Easy) ve B3.3 (keys).**

```powershell
scripts\check.ps1 -Full
```

## B3.0: Danza'nın tempo haritası

Proje sahibi yeni click'i dinledi: 37. saniyeden sonra click'ler kick'lerin üstüne oturuyor, yüksek click "1" gibi geliyor.

"228 ms intro kayması" iki ayrı şeymiş, ikisi de tempo kayması değil:

1. **Tracker off-beat'e kilitleniyor.** 37-52 sn'de vuruşlar yarım vuruş (230,8 ms) uzakta duruyor. Grid doğru: 37 sn sonrasında davul onset'lerinin %97-100'ü gridde, şarkının sonundan kurulan grid o bölümü -3,5 ms ile tahmin ediyor.
2. **İlk 36,9 sn şarkının parçası değil.** Burada kısık, gridi 100,00 BPM olan bir arka plan müziği var (davul R=0,75, şans 0,15), 24-36 sn'de neredeyse yalnızca `vocals` stem'i duyuluyor. Şarkı 37,1 sn'de başlıyor. Dosyanın klip kaydı olması muhtemel (kulakla doğrulanmadı).

Teşhis sırasında asıl hata çıktı: **grid yarım vuruş kayıktı.** Dembow'un snare'leri tracker'ı çekiyor, kick ise gridin off-beat'lerinde. Notalar yine 16'lıkta kaldığı için hiçbir onset ölçümü bunu göremez; yanlış olan vuruş ve ölçü çizgileri, click ve "önce vuruşlar" önceliğiydi.

| Danza | Önce | Sonra |
|---|---|---|
| En kötü bölge, 36,9 sn sonrası | 228 ms | 9 ms |
| Onset'i olan vuruş | %56 | %93 |
| Click altındaki kick gücü (36,9 sn sonrası) | 0,75 | 3,01 |
| İlk downbeat | 1,806 sn | 1,114 sn (düşük güven uyarısıyla) |
| Tempo | 129,975 | 129,975 |

`--bpm 130` karşılaştırması, override gerekmiyor: 130,000'da davul onset'leri şarkı boyunca -15'ten +14 ms'ye geziyor, 129,975'te en fazla 2,1 ms. Tek tempolu `--bpm 130` yolunda da grid taşındı, ama tüm şarkıda medyan kayma 12 ms (otomatik, 36,9 sn sonrası: 3,7 ms) ve onset'li vuruş %81 (otomatik: %93).

**Yeni kurallar:**
- `check_beat_phase` (`audio/meter.py`): kick off-beat'te ≥2 kat güçlü, snare vuruşları işaretlemiyor (off/on ≥0,8), davul stem'i gerçekten var, bölümlerin en az yarısı aynı yönde, z≥2 ise grid yarım vuruş ileri alınır. `--bpm` ile de çalışır.
- `_unfit_lead_in` (`audio/tempo.py`): olaylar reddedilmişse, onset'leri gride oturmayan başlangıç ölçüm dışında kalır, ayrı raporlanır ve uyarı verir. Kayma en yakın sekizliğe göre ölçülür. Harita kararına karışmaz.
- Ölçü fazları beraberse (1 standart hatadan az) sert kick'li faz seçilir.

| Şarkı | Kick off/on | Snare off/on | Karar |
|---|---|---|---|
| Danza | 3,83 | 0,93 | Taşındı |
| Şarkı Testi | 1,42 | 0,58 | Aynı |
| Californication | 0,64 | 0,41 | Aynı (insan vuruşlarının %100'ü bizimkilere daha yakın) |
| LastResort | 0,56 | 0,32 | Aynı |
| Toca | 0,13 | 0,56 | Aynı |

Toca, LastResort, Şarkı Testi ve Californication'ın tempo haritaları, `final` ölçümleri ve karar metinleri değişmedi. LastResort ve Şarkı Testi'nin `notes.chart` dosyaları bayt bayt aynı.

**Sınırlar:**
- Eşikler beş şarkıdan geliyor. Taşınan tek örnek Danza ve onun insan chart'ı yok; doğruluğu kick ölçümüne ve proje sahibinin kulağına dayanıyor.
- Kick dışında üst bantta sesi olmayan sade bir dembow yakalanmaz: yanlış gridde snare'leri backbeat'e benzer. O şarkı bugünkü gibi yarım vuruş kayık kalır (`test_known_limit_...`).
- Yalnızca yarım vuruş düzeltilir. Sentetik bir groove'da tracker çeyrek vuruşa da kilitlendi, gerçek şarkıda görülmedi.
- Danza'nın ölçü fazı beraberlikten seçildi, `low_confidence` açık kalıyor.

**Proje sahibinin kararları:**
- İlk 36,9 sn için ayrı 100 BPM bölgesi eklenmeyecek.
- B3.1 için kesin kural: şarkıya ait olmayan başlangıca hiçbir enstrümanda nota girmez, bu test edilir. Bölgenin başına `[Events]`'e bir section işareti ("Intro") konur.
- `build --click-overlay` click dosyasını normal yoldan üretecek.

## Tamamlanan fazlar

| Faz | İçerik | Commit |
|---|---|---|
| A | Stem ayrıştırma, paketleme, basit gitar chart'ı | `a5fdd64` |
| Tempo kontrolü | Click overlay, `--bpm`, `--max-beat-drift-ms`, tempo olaylarının gerekçesi | `5757a4d`, `cd0fb16`, `392df8e` |
| B1 | Ölçü, akor, sustain, Viterbi fret eşleme, vokal sızıntısı (Expert gitar) | `fc4749c` |
| Tekrarlanabilirlik | Sabit seed, önbellek anahtarı, hızlı pre-commit, `check.ps1 -Full` | `9777680` |
| B2 | Hard, Medium, Easy (gitar) | `5668319` |
| B3.0 | Danza tempo haritası: beat fazı, uymayan başlangıç | bu commit |

Proje sahibi LastResort ve Şarkı Testi'nin güncel Hard ve Medium sürümlerini de çaldı: akorlar rahat, fret dağılımı dengeli, senkron iyi.

## Son ölçüm (Californication)

Bu şarkı `train`, ayarlar onunla yapıldı, yani skorlar iyimser.

| | Expert | Hard | Medium | Easy |
|---|---|---|---|---|
| Nota F1 | 0.794 | 0.729 | 0.640 | 0.745 |
| "Önce vuruşlar" taban skoru | – | 0.684 | 0.613 | 0.383 |
| "Her N'inci" taban skoru | – | 0.551 | 0.403 | 0.257 |
| En büyük şerit sapması | 0.151 | 0.057 | 0.093 | 0.077 |
| Yön (insan şerit değiştirince) | 0.62 | 0.64 | 0.56 | 0.51 |
| Akor oranı (ben / insan) | %50 / 59 | %42 / 58 | %42 / 57 | %0 / 0 |
| Otomatik HOPO (ben / insan) | %3.0 / 0.9 | %0 / 0.2 | %0 / 0 | %0 / 0 |

Pre-commit hook 39–58 sn sürüyor (hızlı testler + validator, makine yüküne göre değişiyor). `-Full` yaklaşık 7 dakika.

## Bilinen sınırlar ve açık konular

- **Tek referans şarkı:** ölçümler ve yumuşak hedefler yalnızca Californication'a dayanıyor, `references/test` boş. Yeni referanslar `test`'e konur, önce ölçülür, hiçbir ayar yapılmaz, sonra proje sahibine sorulur.
- **Expert yeşil-sarı şerit sapması:** yeşil %10 / 25, sarı %30 / 19, ikisi de ±10 dışında ve yalnızca uyarıyor. Expert ayar taramasında ±10'a giren bir ayar bulunamadı, çalınmış sürümü değiştirmemek için Expert'e dokunulmadı.
- **Hard akor oranı %42 / %58:** şerit düzeltmesi yalnızca freti değiştirdiği için bu oranı etkilemedi. Expert'te de oran insandan düşük (%50 / 59).
- **Distortion akor eşiği geçici önlem:** medyana bağlı eşik devreye girince terminalde ve `analysis.json`'da uyarıyor. Sert distortion'da akor doğruluğu ölçülmedi. `basic-pitch` eklenmedi: Python 3.11'e kadar destekliyor ve TensorFlow istiyor.
- **GPU determinizmi doğrulanmadı:** aynı stem'ler yalnızca bu makinenin CPU'sunda bit bit doğrulandı. Cihaz türleri önbellek paylaşmıyor.
- **Yön hedefi:** gitar Expert'te insan şerit değiştirince %62. %65 hedefi test referanslarına ertelendi.
- **Otomatik HOPO:** LastResort Expert %15.9 ve Hard %3.6, Şarkı Testi Expert %10.6, hedefler aşıldığı için uyarıyor. Davranış değiştirilmedi. `N 5` düzeltmesi gerçek şarkılarda hiç gerekmedi, yalnızca sentetik testte çalıştı.
- **Şerit hedefi başka şarkılarda sert olabilir:** build, Californication'ın paylarıyla karşılaştırıyor. LastResort Easy'de kırmızı %73, ama oynarken tek düzelik hissedilmedi. Test referanslarıyla yeniden ayarlanmalı.

## Bekleyen kararlar ve ön tercihler

Bunlar proje sahibinin ön tercihleri. B3 bu varsayımlarla başlar.

| Karar | Ön tercih |
|---|---|
| Bas için vokal süzgeci | Kapalı |
| Basta `pyin` | Kullanılsın |
| Keys | Sentetik testle eklensin, raporda "gerçek veriyle doğrulanmadı" olarak işaretlensin |
| Toca Toca piyanosu | "Yok" kalsın, eşik değişmesin |

## B3 planı: bas, keys ve gitarsız şarkılar

### Ölçümler

| Bas, Californication (ayar yok) | Expert | Hard | Medium | Easy |
|---|---|---|---|---|
| Nota F1 | 0.80 | 0.75 | 0.76 | 0.63 |
| "Önce vuruşlar" | – | 0.65 | 0.55 | 0.39 |
| Yön (insan değiştirince), şimdi | 0.44 | 0.48 | 0.33 | 0.56 |
| Yön, gerçek perde ile (`librosa.pyin`) | 0.61 | 0.66 | 0.61 | 0.67 |

- **Bas iyi başlıyor ama yönü zayıf.** Tek sesli olduğu için `pyin` işe yarıyor. Yeni bağımlılık gerektirmiyor, 324 sn'lik şarkıda 33 sn ekliyor.
- **Vokal süzgeci basa zarar veriyor.** Californication'da sildiği 29 notanın %83'ü gerçek, kapalıyken F1 0.81. Danza'da 674 notanın 153'ünü siliyor.
- **Piyano:** beş şarkının hiçbirinde piyano stem'i "var" çıkmıyor (-65, -59, -64, -54, -19 dB). İnsan klavye chart'ı da yalnızca 17 konum. Keys gerçek veriyle doğrulanamıyor.
- **Danza ve Toca:** gitar yok (-44 / -58 dB), bas var (-10 / -9 dB). Bugün ikisi de "No requested instrument produced a chart" hatasıyla, çıkış kodu 2 ile duruyor.

### Kabul kriterleri

**Kesin (kodda, test edilir):**
1. Danza ve Toca derlenir ve validator'dan geçer: `diff_guitar = -1`, `diff_bass ≥ 0`, gitar bölümü yok, gitar stem'inin sesi `song.ogg`'da.
2. Hiç çalınabilir enstrüman yoksa açıklamalı hata verir, klasör bırakmaz.
3. B2'nin kesin kuralları bas ve keys için de geçerli.
4. Bas her seviyede akorsuz. İnsanda 918 konumun hiçbirinde akor yok, bizde bugün Toca'da %2 var.
5. Gitar değişmez: LastResort ve Şarkı Testi'nin gitar bölümleri bayt bayt aynı kalır.
6. Keys: stem varsa dört seviye üretilir, yoksa chart çıkmaz ve sesi `song.ogg`'a gider.

**Yumuşak (bas için kendi tablosu, uyarır):**
- İnsan basından: yoğunluk %72 / 47 / 27, her şerit ±10, sustain ve HOPO payları.
- Sustain: insan Medium ve Easy'de neredeyse hiç kullanmıyor (%1), bizde %9–11.

**Ölçüm hedefleri (Californication basında):**
- F1 şimdiki değerlerin altına düşmez ve "önce vuruşlar"ı geçer.
- Yön her seviyede ≥ 0.60.
- En büyük şerit sapması Hard, Medium ve Easy'de ≤ 0.10.

**Oyun:** Clone Hero iki şarkıyı da bozuk saymaz, bot `Bass` ile dört seviyeyi çalar, proje sahibi en az bir şarkıda Easy ve Hard'ı çalar.

### Test planı

**Sentetik:**
- Bilinen perde dizisiyle bas: çıkan ve inen hat doğru yönde gider, sessiz bölümde yedek davranış çalışır.
- Rastgele ağırlıklarla bas kesin kuralları: analiz akor duysa bile akor çıkmaz.
- Sessiz gitar + bas: klasör, `song.ini`, ses dağılımı. Gitar ve bas ikisi de yoksa hata ve boş çıktı.
- Güçlü piyano stem'i: `[ExpertKeyboard]` ve dört seviye. Zayıf stem: chart yok.
- Üç enstrüman aynı `[SyncTrack]`'i paylaşır.
- Config, enstrüman başına da kesin kuralları gevşetemez.

**`evaluate`:** bas ve keys insanla ayrı raporlanır, "her N'inci" taban skoru yanında kalır. Referansta `PART BASS` yoksa rapor bozulmaz.

**`-Full` içinde gerçek:** Danza, Toca ve Californication basıyla uçtan uca build.

**Dosyalar:**
- Yeni: `audio/bass_pitch.py`, `tests/test_bass.py`
- Güncellenecek: `chart/charter.py`, `chart/instruments.py`, `chart/difficulty.py` + `.toml`, `pipeline.py`, `evaluation/`

### Riskler

- Danza ve Toca'nın insan chart'ı yok. Derlenip çalındığını gösterirler, doğruluğunu değil.
- Reggaeton'da bas stem'ine kick karışabilir, bunu ancak kulak söyler.
- Bas hedefleri de tek şarkıdan geliyor, `references/test` hâlâ boş.
