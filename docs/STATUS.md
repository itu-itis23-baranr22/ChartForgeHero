# Proje durumu

Faz C (davul) devam ediyor, C.0, C.1 ve C.2 adımlarına bölündü ve her birinin sonunda onay bekleniyor. Şartname ve alınan kararlar `docs/SPEC.md` dosyasında.

## Şu anki adım

**C.0 bitti: davul formatı, yazıcı, validator ve referans okuyucu (ses yok). Onay bekliyor. Sırada C.1: Expert sınıflandırma.**

B3 bitti (`2e91ece`): bas ve keys chart'lanıyor, şarkının gitara ihtiyacı yok.

Proje sahibi Danza'nın güncel bas Hard'ını çaldı: ritim rahat, sekizlik notalar doğal geliyor, sıkışıklık yok.

Proje sahibi Danza'nın bas Expert'ini çaldı: senkron iyi, 37-38 sn'deki hayalet notalar rahatsız etmiyor. Seviye kuralı kapalı kalıyor.

Proje sahibi Toca'nın bas Easy ve Hard'ını çaldı: vuruşlar ve zamanlama iyi, tekdüzelik rahatsız etmiyor, turuncu doğal geliyor. "Turuncu = tek perde" uyarısı yumuşak kalıyor: reggaeton'da tekrarlı bas için bu doğal.

## Faz C planı: davul (onaylandı, 2026-11-10)

**Düzen: 4-lane Pro**, cymbal bayrakları ilk sürümde. İlk şartnamedeki "5-lane" bir yazım hatasıydı, kastedilen 4 pad + kick (`SPEC.md` 2. ve 32. karar). Her davul chart'ıyla `song.ini`'ye `pro_drums = True` yazılır, `five_lane_drums` hiç yazılmaz.

| Parça | Gem | `.chart` |
|---|---|---|
| Kick | kick | `N 0` |
| Snare | kırmızı | `N 1` |
| Hi-hat | sarı cymbal | `N 2` + `N 66` |
| Ride | mavi cymbal | `N 3` + `N 67` |
| Crash | yeşil cymbal | `N 4` + `N 68` |
| Yüksek / orta tom | sarı / mavi tom | `N 2` / `N 3` |
| Yer tomu | yeşil tom | `N 4` |

Kırmızı hiçbir zaman cymbal olmaz. Yazılmayanlar: `N 5` (5-lane yeşil), `N 32` (2x kick), accent, ghost, roll, fill, sustain.

**Referans:** Californication'da insan davul chart'ı var (Harmonix, `pro_drums`, `PART DRUMS`). Expert 1426 konum, 1942 gem: snare %38, mavi cymbal %26, sarı cymbal %18, kick %15, yeşil cymbal %2, tom %1. Bu şarkı `train` sayılıyor. `references/test` boş. Yalnızca 16 tom gem'i var, yani tom ölçülemez.

**Bellekte prototip** (eşikler bu şarkıda seçildi, iyimser):

| Sınıf | En iyi yöntem | F1 | Diğer yöntem |
|---|---|---|---|
| Herhangi bir vuruş | `detect_onsets` | 0,907 | |
| Kick | NMF | 0,885 | bant 0,753-0,795 |
| Cymbal | 7-11 kHz bandı | 0,858 | NMF 0,618 |
| Snare | 150-600 Hz bandı | 0,760 | NMF 0,749, çok bantlı 0,723 |

Hi-hat ile ride sönme süresinden ayrılıyor: sarı cymbal ortanca 70 ms, mavi cymbal 453 ms, AUC 0,91.

**İnsanın indirgemesi:** konum zinciri %100, gem zinciri %99-100. Yoğunluk %76 / 64 / 54. Her seviyede en fazla 2 pad. Easy'de kick asla pad'le birlikte değil. 16'lıklar Hard'da %33, Medium ve Easy'de %0. Kalan pay: kick %86 / 80 / 26, snare %55 / 32 / 32, sarı cymbal %97 / 97 / 17, mavi cymbal %97 / 97 / 97.

**Sınıflandırma (C.1), karma yöntem:** vuruşlar `detect_onsets` ile, kick NMF ile, cymbal 7-11 kHz bandından, snare 150-600 Hz bandından. Bir vuruş aynı anda birden çok gem olabilir (kick + hi-hat). Hi-hat ile ride sönme süresinden ayrılır. Crash: güçlü vuruş + uzun sönme + kick. Tom: 80-400 Hz'te perdeli ve uzun sönen vuruş. Yeni paket yok, NMF birkaç satır numpy.

**Kabul kriterleri:**
- Expert, Californication: vuruş konumu F1 ≥ 0,85; kick / snare / cymbal F1 ≥ 0,80 / 0,70 / 0,80; hi-hat ile ride'da doğru şerit ≥ %75; en büyük gem payı sapması ≤ 0,12.
- Alt seviyeler: "önce vuruşlar" ve "her N'inci" taban skorlarını geçer, gem payı sapması ≤ 0,10. Sayısal F1 alt sınırları C.2'de ölçülüp proje sahibine sunulur.
- Eşikler stem'in kendi güçlü vuruşlarına göreli, yoğunluğu sabitleyen eşik yok. Aynı desen iki farklı ses seviyesinde aynı vuruşları verir (test edilir).
- Yön, HOPO ve sustain davulda ölçülmez. Sınıf başına F1 asıl ölçü; konum F1 şeridi görmez.

**Kesin kurallar** (kodda ve validator'da; `drum_*.toml` dosyaları gevşetemez):
- Zincir: konum ve gem bazında Easy ⊂ Medium ⊂ Hard ⊂ Expert. Gem yer değiştirmez: kick kick, cymbal cymbal kalır.
- El sınırı: her seviyede bir konumda en fazla 2 pad (+ kick).
- Hard ve Medium: bir konumda en fazla 2 gem. Easy: kick pad'le aynı konumda olmaz.
- Medium ve Easy: 16'lık yok.
- Sustain yok, başlangıca nota yok, sonuç deterministik.

**Yumuşak** (`drum_difficulty.toml`, yalnızca uyarır): yoğunluk, gem payları ±10, vuruş üstü oran, en kısa aralık. Hangi vuruşun kalacağını önem puanı seçer; 2. ve 4. vuruştaki snare korunur, hayalet snare'ler önce gider.

**Proje sahibinin ekleri:**
- Sınıflandırıcı `.sng`'deki gerçek davul kanallarına karşı da ölçülür (`drums_1` kick, `drums_2` snare, `drums_3` diğerleri). Teşhis için, kabul kriteri değil.
- Göreli eşik kuralı kabul kriteri; iki seviyedeki aynı desenle test edilir.
- NMF'nin build süresine eklediği süre C.1 raporunda verilir.
- Tom ve crash "doğrulanmadı" diye işaretlenir (`analysis.json` ve terminal).
- Gitar ve bas bayt bayt aynı kalır (`-Full`'da hash).
- Davul ağırlıkları ve eşikleri ayrı `drum_*.toml` dosyalarında; config kesin kuralları gevşetemez.

**Gerçeği olmayan şarkılar** (Danza, Toca, LastResort): validator, bot önizleme, sınıf başına click'li kulak testi dosyası. Proje sahibi en az bir şarkıda Easy ve Hard'ı çalar.

**Riskler:** eşikler ve kalan paylar tek şarkıdan; reggaeton'un 808 kick'i farklı; vokal ünsüzleri cymbal bandına, bas kick bandına sızabilir; NMF cymbal kalıbında bozuldu, yalnızca kick için; kick ile hi-hat aynı anda maskelenebilir; bot için oyuncu adı (`Drums` mı `ProDrums` mı) oyunda denenecek.

**Sıra** (her adımın sonunda onay):
- **C.0:** format, yazıcı, validator, referans okuyucu (ses yok).
- **C.1:** Expert sınıflandırma ve kulak testi dosyası.
- **C.2:** Hard, Medium, Easy, bot önizleme ve proje sahibinin çalması.

## C.0: davul formatı, yazıcı, validator, referans okuyucu

Ses analizi yok. Build davulu henüz chart'lamıyor ("not implemented yet" uyarısı, sesi `drums.ogg`'da).

**Model ve yazıcı:**
- `core/drums.py`: `DrumGem` (kick, kırmızı, üç tom, üç cymbal), `DrumPiece` (kitin sekiz parçası) ve onaylanan eşleme `GEM_FOR_PIECE`. `ChartNote`'un yeni `cymbal` alanı yalnızca 2-4. şeritte olabilir.
- `.chart` yazıcısı cymbal'e `N 66` / `67` / `68` ekliyor. Davulda force (`N 5` = 5-lane yeşil), tap, sustain ve open notayı reddediyor. Diğer enstrümanlarda cymbal'i reddediyor.
- `song.ini`: davul chart'ı varsa `pro_drums = True`. Davulsuz şarkının `song.ini`'si değişmedi.

**Validator** (yazıcıdan bağımsız, yalnızca dosyaya bakar):
- Davulda yalnızca `N 0-4` ve `N 66-68`. `N 5` "5-lane yeşil" diye reddedilir; `N 32`, accent ve ghost da reddedilir. Sustain'li davul notası ve altında pad olmayan cymbal bayrağı hata.
- Kesin kurallar: konum ve gem zinciri, her seviyede en fazla 2 pad, Hard ve Medium'da en fazla 2 gem, Easy'de kick + pad yok, Medium ve Easy'de 16'lık yok. Bunları üreten kod henüz yok, C.2'nin çıktısını bağımsız denetleyecek.
- `song.ini`: davul varsa `pro_drums = True` şart, `five_lane_drums` her durumda hata.
- Kırmızı cymbal `.chart`'ta yazılamaz (bayrağı yok). Model ve yazıcı reddediyor.

**Referans okuyucu,** oyunun sırasıyla: önce `song.ini` etiketleri, sonra notalar.
- `.mid`: sarı, mavi ve yeşil varsayılan olarak cymbal, 110-112 tom işaretleri tom yapar. Tom işaretleri tek başına chart'ı Pro yapar.
- `.chart`: pad varsayılan olarak tom, 66-68 bayrağı cymbal yapar. Bayrak ya da `pro_drums` chart'ı Pro yapar.
- Pro olmayan chart'ta cymbal yok, pad'ler tom okunur. 5-lane (`five_lane_drums`, `.mid`'de 101, `.chart`'ta `N 5` ya da sustain) ve disco flip (`[mix N drumsXd]`) okunmaz, nedeni yazılır. 2x kick (95, `N 32`) Expert'e katılmaz, ayrıca sayılır.
- Kaynak: `GuitarGame_ChartFormats` @ `3d36405748`: `chart-format/Tracks/Drums.md`, `mid-format/Tracks/Drums.md`, `song-ini/Standard-Tags.md`.

**Californication, okuyucuyla yeniden sayıldı.** Prototip ayrı bir betikti; sayılar birebir aynı.

| | Expert | Hard | Medium | Easy |
|---|---|---|---|---|
| Konum | 1426 | 1081 (%76) | 910 (%64) | 766 (%54) |
| Gem | 1942 | 1550 | 1361 | 914 |
| Kick / kırmızı | %14,8 / 38,2 | %15,9 / 26,2 | %16,9 / 17,7 | %8,3 / 26,4 |
| Sarı / mavi / yeşil cymbal | %18,1 / 25,9 / 2,1 | %22,8 / 31,5 / 3,0 | %25,9 / 35,8 / 3,4 | %6,8 / 53,3 / 5,0 |
| Tom gem | 16 | 9 | 4 | 2 |
| 16'lıktaki konum | 511 | 167 | 0 | 0 |

- Expert'teki 16 tom'un hepsi sarı. Tom işaretleri: 7 sarı, 4 mavi, 1 yeşil aralık.
- Disco flip yok (`[mix N drums3]`), 2x kick yok.
- İnsan, kesin kurallarımızın hepsine uyuyor, tek bir fark var: Hard'ın gem'lerinin %1'i Expert'te aynı tick'te başka bir gem. Gem zinciri Hard→Expert %99,0, Medium→Hard %99,9, Easy→Medium %100; konum zinciri her yerde %100. Bizim kuralımız insandan sıkı.

**Gitar ve bas:** `-Full`'a bas için de bayt bayt hash eklendi: Danza, Toca, LastResort ve Şarkı Testi'nin `[SyncTrack]` + dört bas seviyesi, `2e91ece`'deki hâliyle. Bas ayar dosyalarının (`bass_fret_weights.toml`, `bass_difficulty.toml`, `quiet_notes.toml`) hash'i hızlı testte. Gitarın iki hash testi zaten vardı. Bas hash'leri `HEAD`'in ayrı bir kopyasından alındı, yeni kod aynısını veriyor.

**Kontroller:** `check.ps1 -Full` geçti: 801 test (719 + 82 yeni), 1031 sn, 7 klasör validator'dan geçti, gitar ve bas hash'leri dahil.

**Değişen testler:**
- `test_validator_accepts_drum_only_values_on_drums`: `N 32` (2x kick) artık reddediliyor, yerine `N 2` + `N 66`.
- `test_drums_are_left_alone`: Easy'de kick + pad artık kesin kural hatası. Aynı amaç (yeşil pad turuncu sayılmaz, Easy'de iki pad olur) kırmızı + yeşil ile sınanıyor.

**Sınırlar:**
- Davul referansı yalnızca `PART GUITAR`'ı olan bir chart'tan okunabiliyor, çünkü yükleyici gitar istiyor. Bugünkü tek referans için sorun değil.
- Disco flip'li bir chart'ın davulu okunmuyor. Format belgesi flip'in Pro notalarına etkisini net yazmıyor.
- `.mid`'de uzun notanın 5-lane sayılması uygulanmadı: belge eşik vermiyor, MIDI'de her notanın uzunluğu var.

## İleride değerlendirilecek fikirler

- **Basta open note (`N 7`):** tekrar eden en alçak notalar için. Proje sahibinin önerisi, uygulanmadı.

```powershell
scripts\check.ps1 -Full
```

## B3.3: Keys

**Gerçek veriyle doğrulanmadı.** Ölçülen beş şarkının hiçbirinde piyano stem'i "var" çıkmıyor ve tek insan klavye chart'ı 17 konum. Build terminalde ve `analysis.json`'da bunu yazıyor (`not_verified_on_real_data`).

Keys gitarın yolunu izliyor: gitarın ayar dosyaları, gitarın vokal süzgeci, akorlar açık. Yumuşak hedefi yok, çünkü gitarın sayıları keys için anlamsız uyarı üretirdi.

**Kabul kriterleri:**
- Stem "var" ise `[ExpertKeyboard]`'dan `[EasyKeyboard]`'a dört seviye ve `keys.ogg`. Stem "yok" ise chart yok, sesi `song.ogg`'da.
- Piyano eşiği değişmez (-18 dB, %25 aktif). Toca piyanosu "yok" kalır (-19,3 dB).
- B2'nin kesin kuralları: konum zinciri, Medium'da en fazla 2 notalı akor ve turuncu yok, Easy'de akor ve turuncu yok, sustain taşmaz. Başlangıca nota girmez.
- Şarkı yalnızca keys ile de derlenir. Hiç çalınabilir enstrüman yoksa açıklamalı hata, klasör kalmaz.
- Üç enstrüman tek `[SyncTrack]` paylaşır.
- `evaluate` keys'i ayrı raporlar. Stem yoksa puanlamaz, referansta keys yoksa rapor bozulmaz.

**Sınırlar:** akor eşiği gitardan geliyor, piyanoda ölçülmedi. Vokal süzgeci piyanoda ölçülmedi. Californication'ın 17 konumluk insan klavye chart'ı puanlanamıyor, çünkü piyano stem'i orada "yok". Proje sahibi bu durumu kabul etti; "Bilinen sınırlar ve açık konular"da açık konu olarak duruyor.

## Validator: bölüm adı koruması

Her enstrüman yalnızca kendi bölüm adıyla yazılabilir: gitar `*Single`, bas `*DoubleBass`, keys `*Keyboard`, davul `*Drums`. GHL ve 6-fret bölümleri hiç üretilmez. Validator bilinmeyen bölüm adlarını zaten reddediyordu, ama adları yazıcıyla aynı tablodan okuyordu; yazıcıda yanlış bir ad validator'dan da geçerdi. Artık kendi tablosu var. Kasıtlı yanlış adlarla test ediliyor (`ExpertGHLGuitar`, `EasyGHLBass`, `ExpertDoubleRhythm`, `expertsingle` ve diğerleri).

## B3.2'ye ek: Hard'da tempoya göre aralık

En kısa aralık 0,25 sn hızlı şarkılarda sekizlik notayı eliyordu. Bas Hard'da artık sekizlik nota aralığı da kabul (`min_gap_beats = 0.5`). 120 BPM'in altında hiçbir şeyi değiştirmez.

| | Hard pozisyon | En kısa aralık | Değişen |
|---|---|---|---|
| Danza (130 BPM) | 403 -> 483 (%60 -> %72, hedef %66-78) | 0,308 -> 0,231 sn | 53 nota çıktı, 133 nota girdi; vuruş üstü %84 -> %70 |
| Toca (126 BPM) | 197 -> 197 | 0,275 -> 0,238 sn | 19 nota değişti |
| Californication (97 BPM) | aynı | aynı | bayt bayt aynı, F1 0,774 |

F1 şartı yalnızca Californication'da ölçülebiliyor ve orada kural devreye girmiyor, yani etkisi insan chart'ıyla ölçülmedi. Expert, Medium ve Easy üç şarkıda da aynı. `Songs`'daki Danza ve Toca bu sürüm.

## B3.2: Bas Hard, Medium ve Easy

Bas artık dört seviye üretiyor ve kendi ayar dosyalarını kullanıyor: `chart/bass_fret_weights.toml`, `chart/bass_difficulty.toml`. Gitarın ayar dosyaları değişmedi, testler hash'lerini sabitliyor.

**Californication bası artık `train`.** Bas ağırlıkları onunla seçildi (240'tan fazla ayar denendi), aşağıdaki skorlar bu yüzden iyimser. `references/test` hâlâ boş.

| Californication bası | Expert | Hard | Medium | Easy | Hedef |
|---|---|---|---|---|---|
| Nota F1 | 0,811 | 0,774 | 0,771 | 0,649 | en az 0,81 / 0,77 / 0,76 / 0,64 |
| "Önce vuruşlar" | – | 0,665 | 0,559 | 0,402 | geçilecek |
| "Her N'inci" | – | 0,618 | 0,396 | 0,233 | |
| Yön, insan değiştirince | 0,725 | 0,711 | 0,690 | 0,685 | en az 0,65 / 0,60 / 0,60 / 0,60 |
| En büyük şerit sapması | 0,103 | 0,075 | 0,048 | 0,052 | en fazla 0,12 / 0,10 / 0,10 / 0,10 |
| Turuncu (ben / insan) | %15,6 / 14,7 | %17,6 / 15,4 | %0 / 0,9 | %0 / 0,8 | Expert ve Hard'da %10-25 |
| El hareketi (ben / insan) | 0,86 / 0,94 | 1,13 / 1,07 | 1,17 / 1,26 | 1,05 / 1,25 | Expert'te 0,60-1,00 |
| Sustain (ben / insan) | %13 / 20 | %18 / 29 | %0,3 / 0,7 | %0,4 / 1,2 | |

Hepsi hedefte. Yumuşak hedeften kaçanlar küçük: Expert sarı %25,1 (üst sınır 24,8), Hard sustain %17,9 (alt sınır 19).

**Turuncu perde dağılımı** (`analysis.json` ve `evaluate`; tek perde %70'i geçerse uyarır):

| | Expert | Hard |
|---|---|---|
| Californication | 143 nota, en sık C3 %34: C3 49, D3 30, E3 17, F3 16, A2 8, D♯3 6, D2 6, E2 5, diğer 6 | 116 nota, en sık C3 %30 |
| Danza | 113 nota, **G2 %85**: G2 96, E2 10, D2 3, A2 2, F♯2 1, G♯2 1 | 42 nota, **G2 %98**: G2 41, A2 1 |
| Toca | 64 nota, **A♯1 %92**: A♯1 59, G♯1 3, A1 2 | 52 nota, **A♯1 %92**: A♯1 48, A1 2, G♯1 2 |

Danza ve Toca'nın ikisi de uyarıyor: bu şarkılarda turuncu pratikte en yüksek sık perdeyi gösteriyor. Californication'da böyle değil, çünkü perde çeşidi çok daha fazla.

**Oyun:** iki şarkı da önizleme modunda botla dört seviyede açıldı. Ekran görüntülerinde dört bas şeridi notaları çalıyor, log temiz. Bot isabet oranı ölçülmedi.

**Danza ve Toca'nın diğer yumuşak uyarıları:** Toca Hard'da turuncu %26 (üst sınır 25), sustain %44 (üst sınır 39), Easy'de kırmızı %47 (üst sınır 45). Şerit paylarının bir kısmı Californication'dan geldiği için bu şarkılarda sert olabilir.

### Turuncu teşhisi

Californication'ın insan basında turuncu %14,7, gitar ağırlıklarıyla bizde %0,1 idi.

**Neden turuncuya hiç çıkmıyorduk:** gitardan gelen ağırlıklar turuncuyu yapısal olarak kapatıyor.
- Şerit önceliği: turuncu 5,63, mavi 3,03. Register hedefi de 3. fretle bitiyor, turuncuya 0,6 daha ekliyor.
- Mavideyken hat yükselince, aralık ne kadar büyük olursa olsun turuncuya çıkmak kalmaktan 1,2 pahalı. Hat 2 ya da 7 yarım ton çıksa da sonuç aynı.
- Cümlenin tepesindeki 45 notanın 43'ü mavide.

**İnsanın turuncusu "en yüksek perde" demek değil:**
- Turuncunun yalnızca %32'si cümlenin tepesinde. Alçak notalara da gidiyor: A1'in 38 notasından 15'i, D2'nin 65'inden 16'sı turuncu.
- Bölüme göre değişiyor: 30 sn'lik dilimlerde %3 ile %31 arasında.
- Bu yüzden payı tutturabiliriz, ama aynı notaları tam tutturamayız.

| Expert, Californication | Gitar ağırlıkları | A | B (seçilen) | İnsan |
|---|---|---|---|---|
| Yeşil / kırmızı / sarı / mavi / turuncu % | 20/26/33/22/0 | 16/29/9/26/20 | 16/22/25/21/16 | 25/27/15/18/15 |
| En büyük şerit sapması | 0,177 | 0,090 | 0,103 | – |
| Yön, insan değiştirince | 0,655 | 0,657 | 0,725 | – |
| El hareketi (nota başına şerit) | 0,66 | 0,84 | 0,86 | 0,94 |
| Bizim turuncunun insanla aynı olanı (şans %10) | – | %25 | %31 | – |
| İnsan turuncusunun yakaladığımız payı | %1 | %51 | %51 | – |
| Danza / Toca turuncu | %0 / %0 | %17 / %23 | %17 / %23 | – |

A: `lane_prior` 1,0, paylar insan + düz karışımı, `register` 0,3, `register_span` 0-4, `hold` 0,5. B: `lane_prior` 0,25, insan payları, `register` 0,3, `register_span` 0-4. Proje sahibi B'yi seçti.

### Kabul kriterleri (onaylandı)

- Kesin: B2 kuralları basta (konum zinciri, Medium ve Easy'de turuncu yok, sustain taşmaz, uzun cümle Easy'de kalır, deterministik). Dört seviyede de akor yok, başlangıca nota yok. Gitar bayt bayt aynı, gitarın ayar dosyaları değişmez. Bas kendi dosyalarını kullanır ve bunlar kesin kuralları gevşetemez. Danza ve Toca dört seviyeyle validator'dan geçer.
- Ölçüm: F1 en az 0,81 / 0,77 / 0,76 / 0,64 ve "önce vuruşlar"ın üstünde. Yön Expert'te en az 0,65, diğerlerinde en az 0,60. En büyük şerit sapması Expert'te en fazla 0,12, diğerlerinde en fazla 0,10. Turuncu Expert ve Hard'da %10-25. El hareketi Expert'te 0,60-1,00.
- Yumuşak tablo (yalnızca uyarır): yoğunluk %72 / 47 / 27, en kısa aralık 0,25 / 0,40 / 0,55 sn, şeritler ±10, sustain Hard'da yaklaşık %29, Medium ve Easy'de yaklaşık %1, Expert HOPO yaklaşık %12. Danza ve Toca için turuncu en fazla %25, tek şerit en fazla %45.
- Oyun: bot `Bass` ile dört seviyeyi çalar, proje sahibi en az bir şarkıda Easy ve Hard'ı çalar.
- Proje sahibinin ekleri: turuncu perde dağılımı raporlanır ve tek perde %70'i geçerse uyarır; bas ağırlıkları ayrı dosyada durur, gitar dosyaları `-Full`'da hash ile denetlenir; Californication bası `train` sayılır.

## B3.1: Gitarsız build ve bas Expert

Danza ve Toca artık derleniyor: validator'dan geçiyor, `diff_guitar = -1`, `diff_bass ≥ 0`, gitar bölümü yok, gitar stem'inin sesi `song.ogg`'da. İkisi de oyunda botla hatasız yüklendi (`--song`, yalnızca yükleme logu; bot çalışı ölçülmedi, insan çalmadı). Önizleme tarama yapmadığı için `badsongs.txt` bu konuda kanıt değil.

| Bas Expert | Danza | Toca | Californication (ben / insan) |
|---|---|---|---|
| Pozisyon | 671 | 274 | 916 / 918 |
| Akor | 0 | 0 | 0 / 0 |
| Yeşil / kırmızı / sarı / mavi / turuncu | %30 / 19 / 23 / 28 / 0 | %38 / 10 / 24 / 28 / 0 | %20 / 26 / 33 / 22 / 0,1 — insan %26 / 27 / 15 / 18 / 15 |
| Sustain | %16 | %32 | %13 / 20 |
| Otomatik HOPO | %9,7 | %3,3 | %9,2 / 12,3 |

Californication bası (`train`, ama bas için hiçbir ayar yapılmadı): nota F1 **0,811** (kesinlik 0,812, duyarlılık 0,810; hedef ≥ 0,80), yön insan değiştirince **0,655** (hedef ≥ 0,60; `pyin` öncesi 0,44), sustain F1 0,604. En büyük şerit sapması 0,177: insan turuncuyu %15 kullanıyor, bizde %0,1. Bu B3.2'nin bas şerit tablosunun işi.

**Değişmeyenler:** Californication gitarı aynı (Expert F1 0,794, seviyeler 0,729 / 0,640 / 0,745). LastResort ve Şarkı Testi'nin `[SyncTrack]` ve dört gitar bölümü bayt bayt aynı, bunu `-Full` sabit hash'le denetliyor. Yeni üretilen chart'larda bunlara `[ExpertDoubleBass]` ekleniyor. Oyundaki kopyalara dokunulmadı.

**Yeni kesin kurallar** (`difficulty.py`, `pipeline.py`, config gevşetemez):
- Bas her seviyede akorsuz. Mapper'da akor şekilleri kapalı, üretilen track ve yazılan dosya ayrıca denetleniyor.
- Şarkıya ait olmayan başlangıca hiçbir enstrümanda nota girmez. Charter notayı düştüğü tick'e göre eler (snap sınırı geçiremez), build her track'i denetler (henüz yazılmamış enstrümanlar dahil), validator da `analysis.json` ve `[SyncTrack]`'ten bağımsız kontrol eder.
- Bölgenin başına `0 = E "section Intro"`, şarkının başladığı ilk net onset'e `section Song` yazılır (Danza'da 37,1 sn). Böyle bir başlangıcı olmayan şarkıda section yazılmaz.

**Click:** `build --click-overlay` artık `debug/debug_click.wav` yazıyor. Danza'da bu dosya, proje sahibinin dinlediği `Danza_click_YENI.wav` ile bayt bayt aynı.

**Sınırlar:**
- Başlangıcın sonu 8 vuruşluk pencere sınırı. Şarkı pencerenin ortasında başlasa ilk notalar en fazla bir pencere kadar kesilebilir. Danza'da kesilen yok: şarkı 37,1, sınır 36,9 sn.
- Sanatçı adları (Don Omar, Fly Project) dosyada yok, elle verildi. Klasör adı kodda `Sanatçı - Şarkı`, yani `outputs\Don Omar - Danza Kuduro\`.

### Kick sızıntısı teşhisi

| | Danza | Toca | Californication |
|---|---|---|---|
| Nota | 671 | 274 | 916 |
| Kick üstünde (şans) | %55 (%15) | %48 (%9) | %34 (%12) |
| Kick üstünde ve kısa veya perdesiz | 7 (%1) | 2 (%1) | 6 (%1), hepsi gerçek |
| Kick üstünde, kendi seviyesinin 9 dB altında, davulun 18 dB altında | 11 (%1,6) | 10 (%3,6) | 5 (%0,5), hepsi gerçek |
| Şüpheli (ikisinin birleşimi) | 16 (%2,4) | 11 (%4,0) | 11 (%1,2), hepsi gerçek |

- **Tarif edilen imza (kısa, perdesiz) neredeyse yok.** Bas stem'indeki onset'lerin çoğu perdeli ve halka süresi uzun.
- **Kick üstünde olmak kanıt değil.** Californication'da kick üstündeki notaların %96'sı gerçek, diğerlerinin %73'ü. Bunları silmek F1'i 0,811'den 0,581'e düşürür. 172 yanlış notanın yalnızca 11'i kick üstünde.
- **Perdeli kick hipotezi desteklenmiyor.** Kick'in baskın frekansı Toca'da 48,4 Hz (G1), ama G1 okunan nota yok. Danza'da 59,2 Hz (A♯1), en sık perdeler arasında yok. Notalar armoniyle değişiyor. A1 ve B1'in kick üstü oranı yüksek (%77, %84), bu tek başına eleyecek kadar güçlü değil.
- **Tek net aday Danza'nın kick'li girişi:** 37,58 ve 38,04 sn. Bas stem'i orada sessize yakın ve kick'in 23 dB altında.
- **Toca'daki alçak notalar:** B0 ve D♯1'de enerji var (oktava göre -7,2 ve -1,5 dB). Californication'ın doğrulanan alçak notaları da benzer (A1 -17,5 dB). Oktav hatası kanıtı yok, ama doğrulanmadı da.

**Proje sahibinin kulak testi** (`outputs\<şarkı>\debug\bas_supheli_notalar.wav`):
- Danza: click'lerden sonra çoğunlukla zayıf, perdesiz bir "tok" sesi. Şüpheli notalar büyük ihtimalle gerçek değil.
- Toca: perdeli, gerçek bas notaları. Silinmemeli.

**Karar:** genel kick süzgeci yok. Yerine seviye kuralı denendi: nota, şarkının medyan bas notasının X dB altındaysa elenir. Koşullar: Californication bası F1 en fazla 0,005 düşer, Toca'nın 11 notasından hiçbiri elenmez. Tutmazsa kural kapalı kalır. Eşik `audio/quiet_notes.toml`'da.

| X | Californication F1 | Toca'nın duyulan notalarından elenen | Danza'nın 16 şüphelisinden elenen |
|---|---|---|---|
| 18 dB | -0,0012 | 1 (67,01) | 3 |
| 20 dB | -0,0017 | 1 (67,01) | 3 |
| 24 dB | -0,0006 | 0 | 2 |

| X | Danza'da elenenler (sn) | Toca'da elenenler (sn) |
|---|---|---|
| 18-21 dB | 38,06 · 49,58 · 66,58 · 201,47 | 1,29 · 22,46 · 33,23 · 67,01 · 70,45 |
| 24 dB | 38,06 · 49,58 · 66,58 | 1,29 · 22,46 · 33,23 · 70,45 |

**Sonuç: kural kapalı** (`enabled = false`, `below_median_db = 24`). 18-20 dB Toca koşulunu tek notayla geçemiyor. 24 dB iki koşulu da geçiyor ama amacını tutmuyor: Danza'nın 16 şüphelisinden 2'sini yakalıyor ve Toca'da kulakla denetlenmemiş 4 notayı siliyor. Asıl neden: Danza şüphelileri medyanın 10,3 dB, Toca'nınkiler 10,6 dB altında, yani bu ölçü ikisini ayıramıyor. "Perde kesinliği + hızlı sönme" de denendi, en fazla 2 Danza notası yakalıyor. Kural kapalıyken de `analysis.json` işaret ettiği notaları listeliyor.

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
| B3.0 | Danza tempo haritası: beat fazı, uymayan başlangıç | `5b04df5` |
| B3.1 | Gitarsız build, bas Expert, başlangıç kuralı, section'lar | `e5aff06` |
| B3.2 | Bas Hard, Medium, Easy, ayrı bas ayarları, turuncu perde dağılımı | `e380ae5` |
| B3.3 | Keys (gerçek veriyle doğrulanmadı), Hard'da tempoya göre aralık, validator bölüm adı koruması | `2e91ece` |
| C.0 | Davul formatı (4-lane Pro), yazıcı, validator, referans okuyucu, bas hash'leri | bu commit |

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

Pre-commit hook 39–80 sn sürüyor (hızlı testler + validator, makine yüküne göre değişiyor). `-Full` B3.3'te 642 sn idi. 2026-11-10'da değişmemiş `2e91ece` 957 sn, C.0 koduyla 1031 sn sürdü: C.0'ın yeni testleri yaklaşık 75 sn ekliyor, gerisi büyük ihtimalle makine yükü (ölçülmedi).

## Bilinen sınırlar ve açık konular

- **Keys gerçek veriyle doğrulanmadı:** piyanosu baskın bir şarkı bulunduğunda keys oyunda ve `evaluate` ile doğrulanacak.
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
- **Danza ve Toca:** gitar yok (-44 / -58 dB), bas var (-10 / -9 dB). B3.1'den önce ikisi de "No requested instrument produced a chart" hatasıyla duruyordu.

### Kabul kriterleri

Hepsi B3.1, B3.2 ve B3.3'te karşılandı. Keys'in durumu için B3.3'e bak.

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
- Reggaeton'da bas stem'ine kick karışabilir, bunu ancak kulak söyler (teşhis: B3.1).
- Bas hedefleri de tek şarkıdan geliyor, `references/test` hâlâ boş.
