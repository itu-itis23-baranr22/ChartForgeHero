# Proje durumu

Faz D (bölümler, preview, star power, vokal) devam ediyor; D.0, D.1, D.2 ve D.3 adımlarına bölündü ve her birinin sonunda onay bekleniyor. Şartname ve alınan kararlar `docs/SPEC.md` dosyasında.

## Şu anki adım

**D.1 kapandı: bölüm tespiti. Proje sahibi 2026-11-12'de onayladı. Sırada D.2: preview noktası; bitince proje sahibi dört şarkının preview'unu dinleyecek.**

D.0 `7251c84`'te kapandı (ölçüm altyapısı; vokal paketlemesi proje sahibince oyunda doğrulandı).

Faz C `1ec287d`'de kapandı (C.2: davul Hard, Medium ve Easy). Proje sahibi 2026-11-11'de C.2'yi onayladı ve LastResort, Danza ve Toca'nın Pro Drums'ını Easy ve Hard'da çaldı: hepsi çalınabilir, hi-hat ve ride şeritleri doğal, Toca Easy tekdüze gelmedi, sorun yok. F1 alt sınırlarını onayladı (testte). `pyin` paylaşımı "ileride" listesinde.

Test hızlandırma `dd05eb0`'da kapandı. C.1 `3029bc8`'de kapandı (Expert davul chart'ı ve kulak testi dosyaları). Proje sahibi 2026-11-11'de C.2'ye geçilmesini istedi; kulak testinin sonucu henüz gelmedi. C.0 `1fd3d91`'de kapandı. Commit mesajlarına Claude imzası eklenmiyor: `.claude/settings.json` (`00681d2`).

B3 bitti (`2e91ece`): bas ve keys chart'lanıyor, şarkının gitara ihtiyacı yok.

Proje sahibi Danza'nın güncel bas Hard'ını çaldı: ritim rahat, sekizlik notalar doğal geliyor, sıkışıklık yok.

Proje sahibi Danza'nın bas Expert'ini çaldı: senkron iyi, 37-38 sn'deki hayalet notalar rahatsız etmiyor. Seviye kuralı kapalı kalıyor.

Proje sahibi Toca'nın bas Easy ve Hard'ını çaldı: vuruşlar ve zamanlama iyi, tekdüzelik rahatsız etmiyor, turuncu doğal geliyor. "Turuncu = tek perde" uyarısı yumuşak kalıyor: reggaeton'da tekrarlı bas için bu doğal.

## Faz D planı (onaylandı, 2026-11-11)

**Bugün var olanlar:** `vocals.ogg` Faz A'dan beri ayrı dosya (vokal stem'i "yok" ise sesi `song.ogg`'da). Bölüm olarak yalnızca şarkıya ait olmayan giriş için `Intro` ve `Song`. Star power yok. Preview karışımın en gürültülü 30 sn'si, ölçüye oturmuyor.

**İnsan chart'ı (Californication, `train`):**
- 15 bölüm (`prc_intro`, `verse_N`, `prechorus_N`, `chorus_N`, `gtr_solo`), biri dışında hepsi ölçü başında, aralarında 6-12 ölçü.
- Star power: gitar 13, bas 12, davul 11, keys 1 ifade. Her biri yaklaşık 1 ölçü, 36 / 36'sı ölçü başında, aralarında ortanca 22-29 sn. Bir ifade enstrümanın dört seviyesinde aynı yerde (MIDI nota 116).
- `preview_start_time` 174,4 sn: ikinci nakarattan 4 ölçü (10 sn) önce. Bizim kuralımız 285,1 sn seçiyor.

**Prototip (yalnızca scratchpad):** ölçü başına öznitelik, kendine benzerlik ve novelty ile bölüm sınırları. ±1 ölçüde F1 0,47-0,63 (ayarsız). "Her N ölçü" saf sınırları ±1 ölçüde en fazla 0,38, ±2 ölçüde 0,62'ye çıkıyor: ±2 ölçü fazla gevşek.

**Sıra** (her adımın sonunda onay):
- **D.0:** referans okuyucu ve `evaluate` bölümleri, star power'ı ve preview'u da okuyup ölçer. Ses analizi yok, build çıktıları aynı kalır.
- **D.1:** bölüm tespiti (`audio/sections.py`), sınırlar ölçü başında, giriş kuralı korunur.
- **D.2:** preview noktası bölümlerden.
- **D.3:** star power (`chart/star_power.py`), dört enstrüman, validator kuralları, oyunda bot ve proje sahibi.

**Proje sahibinin kararları:**
1. Bölüm adları yapısal harfler: tekrar eden bölüm aynı harf (`section A1`, `section B1`, `section A2`...), event metinleri ASCII. Giriş `Intro` kalır.
2. Star power dört enstrümanda, ifade başına 1 ölçü, yaklaşık her 20-30 sn. Davul star power'ının oyunda nasıl açıldığı (fill gerekip gerekmediği) D.3'te mutlaka doğrulanır; fill gerekiyorsa seçenekler sunulur.
3. Şarkı sözü yazılmaz ("İleride" listesinde).
4. Preview: tekrar eden en enerjik bölümün ikinci kez başlamasından 4 ölçü önce. Bölüm bulunamazsa bugünkü "en gürültülü pencere" kuralı, ölçüye oturtularak.
5. Sınır F1 eşiği D.1'de ölçülüp önerilir; 0,55 taban. "Her N ölçü" taban skoru her durumda geçilmeli.
6. Dokusu az değişen şarkılarda (Danza, Toca gibi) yalnızca `Intro` / `Song` yazılıyorsa bu uyarı olarak raporlanır; zorla bölüm üretilmez.

**Kabul kriterleri (plan):**
- Kesin: nota satırları (`N`) bayt bayt aynı, yalnızca `E` ve `S 2` satırları eklenir; bölüm ve star power ölçü başında; girişte hiçbir şey yok; star power ifadeleri çakışmaz, içinde nota olmayan ifade yazılmaz; preview girişte değil, 30 sn şarkıya sığar.
- Ölçüm (Californication, `train`): sınır F1 ±1 ölçüde ≥ 0,55 ve her "her N ölçü" taban skorunu geçer; en kısa bölüm ≥ 4 ölçü.
- Yumuşak: dakikada 2-5 bölüm; star power dakikada 1,5-3 ifade, ifade başına nota.
- Oyun: bot dört enstrümanda star power toplar; proje sahibi en az bir şarkıda star power'ı toplayıp açar.

## D.1: bölüm tespiti

**Proje sahibinin kararları (2026-11-12):** alıştırma modunda bölüm başları gerçek değişimlere denk geliyor, sorun yok. Sınır F1 eşiği Californication'da ≥ 0,70 onaylandı ve teste yazıldı. `Song` bölümü de harflere katılıyor: `Song` olarak yazılıyor ama başlattığı kısım `A1` sayılıyor, sonradan dönerse `A2` görünüyor (terminalde `Song (A1)`, `analysis.json`'da `song_part`).

**Harf eşiği taraması (2026-11-12).** Proje sahibinin sorusu: pop ve reggaeton'da nakarat birkaç kez döner, 0,6 eşiği fazla katı olabilir mi? Sınırlar build'inkiler, yalnızca harf eşiği değişti. Benzerlik, iki bölümün ölçüleri baştan yan yana konunca ortalama benzerlik (-1 ile 1 arası; build bunu kullanıyor).

| Eşik | Californication: aynı harfli çiftlerden insanda aynı tür olanlar (P) | Aynı tür çiftlerden aynı harf alanlar (R) | Danza | Toca | LastResort |
|---|---|---|---|---|---|
| **0,60** (bugün) | **0,857** (14 çift) | 0,387 | Song(A1) B1 C1 D1 E1 F1 G1 H1 C2 I1 H2 | A1 B1 C1 D1 E1 F1 G1 D2 H1 I1 | A1 B1 C1 D1 E1 F1 G1 H1 I1 D2 J1 |
| 0,55 | 0,722 (18) | 0,419 | Song(A1) B1 C1 D1 E1 F1 G1 E2 C2 H1 E3 | aynı | A1 B1 C1 D1 E1 F1 G1 A2 H1 D2 I1 |
| 0,50 | 0,636 (22) | 0,452 | Song(A1) B1 C1 B2 D1 C2 E1 D2 C3 F1 D3 | A1 B1 C1 D1 E1 F1 E2 D2 B2 C2 | A1 B1 C1 D1 C2 E1 F1 A2 G1 D2 H1 |
| 0,40 | 0,652 (23) | 0,484 | 0,50 ile aynı | 0,50 ile aynı | A1 B1 C1 D1 C2 E1 F1 A2 C3 D2 G1 |
| 0,30 | 0,404 (47) | 0,613 | 0,50 ile aynı | A1 B1 C1 A2 D1 E1 D2 A3 B2 C2 | 0,40 ile aynı |

0,45, 0,50 ile her şarkıda aynı; 0,35, 0,30 ile aynı; 0,25 ve altında Californication'ın 17 bölümünden 14'ü tek harf.

**Eşiğin hemen altındaki çiftler** (0,40-0,60):
- Californication: 0,56 verse_1'in son 4 ölçüsü ~ chorus_1'in ikinci yarısı; 0,56 intro ~ chorus_1'in ikinci yarısı; 0,55 verse_1 ~ verse_3 (ikisi de 4 ölçülük parçalar); 0,51 intro ~ intro. İnsan bunlardan yarısını aynı, yarısını farklı tür sayıyor. Hepsi 4 ölçülük, intro'ya benzeyen bloklar: müzikte aynı riff olabilirler, insan ise işlevine göre adlandırıyor (dinleyerek doğrulanmadı). Harf verme açgözlü olduğu için bir blok gruba girince ona benzeyen diğerleri de giriyor; 0,55'te dört blok tek harf oluyor ve P 0,86'dan 0,72'ye düşüyor.
- Danza: 0,58 1:51.9 ~ 3:37.2 (sonuncusu -21 dB, sessiz kapanış), 0,55 1:51.9 ~ 2:36.2, 0,55 1:20.5 ~ 2:04.8, 0,55 0:51.0 ~ 1:35.3.
- Toca: 0,53 0:07.9 ~ 1:58.4, 0,50 0:53.6 ~ 1:27.9, 0,50 0:21.3 ~ 2:11.7.
- LastResort: 0,55 0:00.0 ~ 2:01.7, 0,51 0:21.0 ~ 0:52.8.

**Sonuç: eşik 0,6'da kaldı.** Pop şarkılarında daha çok tekrar yakalayan her eşik (0,55 ve altı) Californication'da insanın ayırdığı kısımları da birleştiriyor: P en az 0,13 düşüyor. Pop şarkılarındaki yeni tekrarların doğru olup olmadığı ölçülemiyor (insan chart'ı yok). 0,6'da dört şarkının hepsinde en az bir tekrar eden harf var: Danza C ve H, Toca D, LastResort D, Californication B, C, F, G, H. D.2'de yedek kural (en gürültülü pencere) bu şarkılarda devreye girmiyor; D.2 raporu kaç şarkıda ve neden girdiğini yazacak. `sections.toml`'daki "0,55-0,75 arasında harfler değişmiyor" notu standartlaştırma alt sınırlarından önceki ölçümdendi, artık geçerli değil; düzeltildi.

Betik ve tam matrisler commit'te değil (scratchpad, `letters_sweep.py`).

**Nasıl bulunuyor** (`audio/sections.py`, ayarlar `audio/sections.toml`, SPEC 38. karar):
- Her ölçü dört şeyle tarif ediliyor: perdeli stem'lerin akoru (chroma), karışımın tınısı (MFCC) ve ses düzeyi, vokalin ses düzeyi. Hepsi şarkı içinde standartlaştırılıyor; ağırlıklar 1 / 1 / 0,5 / 0,5.
- Ölçülerin birbirine benzerliğinden, bir ölçü çizgisinin önündeki 4 ölçü ile arkasındaki 4 ölçünün ne kadar farklı olduğu hesaplanıyor (Foote'un dama tahtası "novelty"si). Değişim 0 (yok) ile 0,5 (ortak hiçbir şey yok) arasında; 0,18'i geçen tepeler, güçlüsü önce, birbirinden en az 4 ölçü uzakta seçiliyor. Sabit bir bölüm sayısı yok: eşiği geçen değişim yoksa bölüm de yok.
- İlk bölüm şarkının sessiz olmayan ilk ölçüsünde başlıyor.
- **Harfler:** bir bölüm, ölçüleri baştan yan yana konunca (köşegen benzerliği) ortalama 0,6'dan benzer olan önceki bölümün harfini alıyor, yoksa yeni harf. Adlar `A1`, `B1`, `A2`..., ASCII; 26 harften sonra `AA`.
- **Giriş kuralı:** şarkıya ait olmayan girişi olan şarkıda `Intro` ve `Song` aynen kalıyor; tespit `Song`'dan sonra başlıyor ve ilk bulunan bölüm `Song`'dan en az 4 ölçü sonra. `Song`'un başlattığı kısım da harf alıyor (`A1`, yazılan ad yine `Song`), sonraki bölümler onunla da karşılaştırılıyor.
- **Düz şarkı:** standartlaştırma, şarkının küçük titreşimlerini bölüme çevirmesin diye her grubun yayılımı duyulabilir bir alt sınırla tutuluyor (chroma 0,05, MFCC 2, ses düzeyi 1 dB, vokal 1 dB; dört gerçek şarkı en az 0,10 / 2,0 / 3,1 / 8,0 yayılıyor, hiç değişmeyen sentetik döngü 0,003 / 0,73 / 0,05 / 0). Döngüde en güçlü değişim 0,01; eşik 0,18. Bölüm bulunmazsa build uyarıyor (terminal ve `analysis.json`), hiçbir bölüm zorla yazılmıyor.
- **Kesin kurallar kodda** (`check_found_sections`) ve validator'da: ölçü başı (`Song` hariç, o şarkının ilk onset'inde), en az 4 ölçü (son bölüm dahil; `Intro`→`Song` hariç), ASCII ad. `sections.toml` 4 ölçüyü yalnızca yükseltebilir; bilinmeyen anahtar reddediliyor.
- Bir şarkı 0,4-0,9 sn sürüyor. Ölçü çizgileri artık `TempoMap.bar_lines`'tan, tespit ve ölçüm aynı çizgileri kullanıyor.

**Californication** (`train`, ayarlar bu şarkıda seçildi, iyimser):

| | Değer |
|---|---|
| Sınır F1, ±1 ölçü | **0,750** (P 0,706, R 0,800; bizim 17, insan 15) |
| "Her N ölçü", şarkı başından (4 / 8 / 16) | 0,250 / 0,250 / 0,083 |
| En iyi saf (insana bakarak) | 0,385 |
| Eşik taraması (0,12-0,21, 8 ölçülük çekirdek) | 0,722-0,765, düz bir plato; seçilen 0,18 ortası |
| Çekirdek 12 / 16 ölçü | en iyi 0,741 / 0,583: kısa bölümleri kaçırıyor |
| Harfler, çift çift insan sınıfıyla | aynı harf verilen çiftlerin %86'sı insanda aynı tür (verse, chorus...), aynı tür çiftlerin %39'u aynı harf |

Tarama, standartlaştırma alt sınırları eklenmeden önce yapıldı; 0,18'deki sonuç onlardan sonra birebir aynı kaldı.

Harfler insanın yapısıyla örtüşüyor: beş verse'ün hepsi C (C1-C5), chorus_1 ve chorus_2 F1 ve F2, prechorus_2 ve prechorus_3 H1 ve H2. Kaçanlar: prechorus_1 (D1, E1), chorus'un ikinci yarısı (G1) ve chorus_3'ün başlangıcı (insan 4:57.6; biz bölümü 4:28.4'teki H2'nin içinde bırakıyoruz).

**Eşik** (proje sahibi onayladı, 2026-11-12; `test_californication_sections_beat_the_naive_boundaries`): Californication sınır F1 ≥ **0,70**, üç taban skoru ve en iyi saf skor da geçilmeli. Ölçülenin 0,05 altı; eşik taramasındaki en düşük değer 0,722.

**Bölümler, dk:sn** (`Songs`'daki kopyalar; Danza'nın kopyasında harfler henüz eski, `Song` harf almadan: `A1 0:51.0`... D.2'de yeniden kopyalanacak):

| Şarkı | Bölümler |
|---|---|
| Danza | Intro 0:00.0, Song (A1) 0:37.1, B1 0:51.0, C1 1:20.5, D1 1:35.3, E1 1:51.9, F1 2:04.8, G1 2:21.4, H1 2:36.2, C2 2:49.1, I1 3:18.7, H2 3:37.2 |
| Toca | A1 0:00.3, B1 0:07.9, C1 0:21.3, D1 0:38.4, E1 0:53.6, F1 1:10.8, G1 1:27.9, D2 1:43.2, H1 1:58.4, I1 2:11.7 |
| Davul Testi - LastResort | A1 0:00.0, B1 0:10.3, C1 0:21.0, D1 0:42.2, E1 0:52.8, F1 1:16.6, G1 1:51.1, H1 2:01.7, I1 2:12.2, D2 2:22.8, J1 2:54.6 |
| Californication (yalnızca `evaluate`) | A1 0:05.1, B1 0:15.4, C1 0:25.4, B2 0:40.6, C2 0:50.6, D1 1:05.6, E1 1:15.5, F1 1:35.2, G1 1:45.2, C3 1:55.1, G2 2:10.0, C4 2:19.9, H1 2:34.9, F2 3:04.5, I1 3:24.3, C5 4:13.6, H2 4:28.4 |

Danza ve Toca'da bölüm bulundu, yalnızca `Intro`/`Song` kalmadı; uyarı yok. En güçlü değişimleri 0,43 ve 0,45 (Californication 0,44). Toca'nın 2:28.9'daki son sınırı eşiğin hemen üstündeydi, standartlaştırmanın alt sınırları gelince düştü.

**Bayt bayt aynı:** üç şarkı yeniden derlendi; `[SyncTrack]`, gitar, bas ve davulun bütün seviyeleri (bütün `N` satırları) ve `song.ini` C.2 sürümüyle aynı, yalnızca `[Events]`'e bölüm satırları eklendi (Danza'nın `Intro` ve `Song`'u yerinde). Gitar ve bas hash'leri `-Full`'da. Üç klasör validator'dan geçti ve `Songs`'a kopyalandı (`notes.chart`, `song.ini`, `.ogg`'ler, `analysis.json`). Danza oyunda botlarla açıldı, log temiz.

**Alıştırma modunda neye bakmalı:** bir bölüm başı müzikte duyulan bir değişime (giriş, verse, nakarat, solo) denk geliyor mu; aynı harfi alan bölümler gerçekten aynı kısım mı; çok kısa ya da gereksiz bölünmüş bir yer var mı. Not için şarkı ve dk:sn yeterli.

**Sınırlar:**
- Tek referanstan: eşik, çekirdek ve harf eşiği Californication'da seçildi.
- Harfler tekrarların ancak %39'unu yakalıyor: yanlışlıkla "aynı" demektense yeni harf veriyor. Eşiği düşürmek pop şarkılarında daha çok tekrar buluyor ama Californication'da yanlış eşleşmeler ekliyor (yukarıdaki tarama).
- Danza'da `Song`'un kısmı (0:38.0, 7 ölçü) sonra dönmüyor: diğer bölümlere en yüksek benzerliği 0,28.

**Değişen testler** (tolerans gevşetilmedi):
- `test_after_an_opening_the_sections_start_after_song`: `Song` artık harf alıyor (proje sahibinin kararı). Önce `A1 32 sn, B1 48 sn` bekliyordu (`Song` karşılaştırılmıyordu), şimdi `song_part == "A1"` ve `B1 32 sn, A2 48 sn`; girişsiz şarkıda `song_part` yok.
- `test_californication_sections_beat_the_naive_boundaries`: sınır F1 tabanı 0,55'ten onaylanan 0,70'e sıkılaştı.
- `test_analysis_records_the_whole_build`: build aşamaları listesine yeni "Find sections" aşaması eklendi; `analysis.json`'un `sections` kaydı da denetleniyor (`song_part` dahil; girişsiz şarkıda boş).
- `test_stages_are_reported_with_durations`: aşama sayısı 7'den 8'e (`[1/8]`, `[8/8]`), "Find sections" aşamasının raporu da denetleniyor.
- `test_evaluate_reports_the_structure`: yalnızca bir mesaj ("henüz bölüm yok" yerine "hiç değişmeyen click izi bölüm almaz"), doğrulama aynı.
- Yeni: `tests/test_sections.py` (26 test).

**Kontroller, commit öncesi (2026-11-12, kararlar uygulandıktan sonra):** `check.ps1 -Full` geçti: 968 test, 606 sn, 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti, Californication'ın 0,70 eşiği dahil. Tepe özel bellek 3,42 GB, en düşük boş RAM 3,9 GB. İlk deneme `test_analysis_records_the_whole_build`'de durdu: `analysis.json`'a eklenen `song_part` anahtarı testin listesinde yoktu; test düzeltildi ve `-Full` baştan geçti.

**Kontroller, onaydan önce (2026-11-11):** `check.ps1 -Full` geçti: 968 test (942 + 26 yeni), 1084 sn, 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti (yeniden derlenen Danza, Toca ve `Davul Testi - LastResort` bölümleriyle), gitar ve bas hash'leri, davul F1 alt sınırları ve Californication bölüm testi dahil. Tepe özel bellek 3,42 GB, en düşük boş RAM 3,7 GB. Değişmeyen 942 test D.0'daki çalışmayla aynı yükte 1046 → 1055 sn (her build'e bölüm aşaması 0,5-1 sn ekliyor), yeni testler 22 sn. İlk `-Full` denemesi `test_stages_are_reported_with_durations`'ta durmuştu (aşama sayısı 7 → 8); test düzeltildi ve `-Full` baştan geçti.

## D.0: ölçüm altyapısı

**Referans okuyucu** (`evaluation/reference.py`): insanın bölümleri (`.mid`'de EVENTS'teki `[section …]` ve `[prc_…]`, `.chart`'ta `E "section …"`; lyric ve diğer olaylar bölüm sayılmaz), enstrüman başına star power ifadeleri (`.mid`'de nota 116, `.chart`'ta Expert bölümündeki `S 2`; davul fill'i `S 64` sayılmaz) ve `preview_start_time` (yok, -1 ya da okunamıyorsa yok sayılır).

**Ölçüler** (`evaluation/structure_metrics.py`):
- Sınır F1: her insan sınırı, bizim tempo haritamızda kendi ölçüsünün uzunluğu kadar toleransla, en yakın önce ve bire bir eşleşir. Tam bir ölçü kaymış sınır da sayılır.
- "Her N ölçü" taban skorları: şarkının başladığı ölçüden her 4, 8 ve 16 ölçüde bir sınır (adil olanlar, kriter bunlar). Ayrıca en iyi saf skor: 4, 6, 8, 12 ve 16 ölçülük periyotlar her başlangıçla denenir ve en iyisi insana bakarak seçilir (iyimser, bilgi için).
- Star power özeti: ifade sayısı, dakikada ifade, ortanca uzunluk (ölçü), ölçü başında olanların payı, ifadeler arası ortanca süre, ifade içindeki Expert nota sayısı (ortanca ve en az).
- Preview: bizim ve insanın başlangıcı, aralarındaki fark, her birinin düştüğü insan bölümü.

**`evaluate`** her şarkı için `structure` sonucunu ve "Structure of …" satırlarını yazıyor. Californication'da bugün:

| | Değer |
|---|---|
| Bölüm | insan 15, bizim 0 (girişi olmayan şarkıda bugün bölüm yok), sınır F1 0 |
| "Her N ölçü", şarkı başından | her 4: 0,250, her 8: 0,250, her 16: 0,083 |
| En iyi saf (insana bakarak) | 0,385 (her 12 ölçüde, 1. ölçüden) |
| Star power, insan | gitar 13 (2,41/dk, 1 ölçü, %100 ölçü başı, ortanca aralık 22,4 sn, içinde ortanca 8 nota), bas 12 (2,22/dk, 26,8 sn, 8 nota), keys 1, davul 11 (2,04/dk, 28,6 sn, 13 vuruş) |
| Preview | bizim 285,1 sn (`prechorus_3`), insan 174,4 sn (`prechorus_2`), 110,7 sn fark |

**Bayt bayt aynı:** pipeline'daki `Intro`/`Song` kuralı `chart/sections.py`'ye, preview hesabı tek bir fonksiyona (`preview_start_ms_of`) taşındı; davranış değişmedi. Danza (girişli) ve LastResort ayrı bir klasöre yeniden derlendi: `notes.chart` ve `song.ini` bayt bayt aynı, bütün `.ogg`'lerin çözülmüş örnekleri birebir aynı. `.ogg` dosyalarının baytları her derlemede farklı (Ogg Vorbis her kodlamada rastgele bir akış numarası yazıyor; D.0'dan önce de böyleydi). `analysis.json`'da farklı olan yalnızca davul analizinin süresi (`analysis_seconds`).

**Vokal, oyunda:** Settings → Audio'da ayrı bir **Vocals** ses kaydırıcısı var (Master, Guitar, Bass, Rhythm, Drums'ın yanında). Proje sahibi denedi: kaydırıcıyı kısınca vokal kayboluyor, paketleme doğru.

**Değişen testler:** yok. Yeni: `tests/test_structure.py` (15 test; biri gerçek, Californication'ın okunan bölüm, star power ve preview değerlerini ve saf taban skorlarını sabitliyor).

**Kontroller:** `check.ps1 -Full` geçti: 942 test (927 + 15 yeni), 1051 sn, 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti, gitar ve bas hash'leri ve davul F1 alt sınırları dahil. Tepe özel bellek 3,42 GB, en düşük boş RAM 3,8 GB. Süre C.2'nin 555 sn'sinin iki katı, ama değişmeyen 927 testin hepsi eşit oranda (1,9 kat) yavaşladı, D.0'la ilgisi olmayan sentetik tempo testi dahil (13,0 → 23,5 sn); yeni testler toplam 3,5 sn. Yani makine yükü.

## C.2: davul Hard, Medium ve Easy

**Nasıl indirgeniyor** (`chart/drum_difficulty.py`, ayarlar `chart/drum_difficulty.toml`, SPEC 36. karar). Her seviye bir üsttekinden yapılıyor: Hard Expert'ten, Medium Hard'dan, Easy Medium'dan.
- **Kalabalık konum:** bir konumda seviyenin izin verdiğinden fazla gem varsa, gem'ler `gem_order` sırasıyla yer veriyor: snare en son gidiyor, sonra crash, ride, kick, hi-hat, tom'lar. Hard ve Medium iki gem tutuyor. Easy birini tutuyor; ikincisini yalnızca snare, crash ya da ride ise tutuyor. Sonuç: Hard'da K+S+Hh → K+S, K+S+Rd → S+Rd; Easy'de K+Hh → K, K+Rd → Rd, K+Cr → Cr, S+Hh → S, S+Rd kalıyor.
- **Hangi konum kalıyor:** en yüksek puanlı önce (ölçüdeki yer, vuruşun gücü, gem ağırlığı), hedef Expert'in %76 / 64 / 54'ü. Bir seviye üsttekini aşamıyor. Konumlar arası en az aralık Hard'da 1/4, Medium ve Easy'de 1/2 vuruş. 2. ve 4. vuruştaki snare her zaman kalıyor; bir flam bir vuruşa iki snare koyarsa yalnızca iyisi korunuyor.
- **Kesin kurallar kodda** (`check_drum_levels`) ve validator'da: zincir (konum ve gem), her seviyede en fazla 2 pad, Hard ve Medium'da en fazla 2 gem, Easy'de kick + pad yok, Medium ve Easy'de 16'lık yok, sustain yok. Toml dosyası bunlardan birine karar veren bir anahtar taşıyamıyor (`max_gems`, `allow_sixteenths`, Easy'de `second_gem_from`'a `kick` reddediliyor). 60 rastgele Expert ve rastgele ayarla denendi; kod ve validator hiç kural ihlali bulmadı.
- **Neden bu değerler:** insanın Californication indirgemesi (`train`). İnsan Hard'da 8'lik ızgaradaki her konumu, 16'lıkların %64'ünü tutmuş, ızgara dışı süslemelerin hiçbirini tutmamış. Medium neredeyse Hard eksi 16'lıklar. Easy'de tek başına hi-hat'lerin %17'si kalmış, ride'ın %100'ü; kick pad'le birlikteyse pad kalmış, pad hi-hat değilse. Ayarlar F1'e göre değil, bu oranlardan seçildi; ölçü ağırlıklarını değiştirmek Californication'da sonucu değiştirmedi (seçimi kurallar ve aralık belirliyor).
- Dört seviyenin hepsi 0,5-1,0 sn sürüyor.

**Californication** (`train`, ayarlar bu şarkının insan chart'ından, yani iyimser):

| | Konum (ben / insan) | Konum F1 | "Her N'inci" | "Önce vuruşlar" | Kick / snare / cymbal F1 | En büyük gem payı sapması |
|---|---|---|---|---|---|---|
| Expert | 1398 / 1426 | 0,919 | – | – | 0,962 / 0,908 / 0,874 | 0,054 |
| Hard | 1062 / 1081 | 0,880 | 0,725 | 0,801 | 0,957 / 0,775 / 0,916 | 0,033 |
| Medium | 745 / 910 | 0,886 | 0,616 | 0,817 | 0,881 / 0,975 / 0,874 | 0,055 |
| Easy | 745 / 766 | 0,833 | 0,515 | 0,802 | 0,549 / 0,975 / 0,691 | 0,076 |

Kabul kriterleri (plan): üç seviye de iki taban skorunu geçiyor, gem payı sapması ≤ 0,10. İkisi de `-Full`'da test ediliyor.

**F1 alt sınırları** (proje sahibi onayladı, 2026-11-11; `test_californication_lower_levels_beat_both_naive_reductions`): Hard ≥ 0,85, Medium ≥ 0,85, Easy ≥ 0,80. Ölçülenin yaklaşık 0,03 altı; ayarlar bu şarkıdan geldiği için daha sıkı bir sınır anlamsız olurdu.

**Californication'da Easy = Medium (745 konum).** Bizim Expert'in %34'ü 16'lıkta (insanınki %18, artı %18 ızgara dışı), bu yüzden Medium kural gereği Expert'in %53'üne iniyor (yumuşak hedef %54-74, uyarıyor). Easy'nin hedefi de %54 olduğu için Easy hiç konum düşürmüyor, yalnızca gem'leri sadeleştiriyor. Konum sayısı insanın Easy'siyle aynı (745 / 766). Hedefi bir üst seviyeye göre koymak denendi (aralık düzeltmesinden önce): Easy 627 konuma iniyor ve F1 0,752'ye düşüyor, "önce vuruşlar"ın altında.

**Gerçeği olmayan şarkılar** (konum, Expert'e oranı, en kısa aralık):

| | Expert | Hard | Medium | Easy |
|---|---|---|---|---|
| Danza | 1073 | 815 (%76), 1/4 vuruş | 687 (%64), 1/2 | 579 (%54), 1/2 |
| Toca | 527 | 401 (%76), 0,41 | 337 (%64), 1/2 | 285 (%54), 1/2 |
| LastResort | 765 | 581 (%76), 1/4 | 446 (%58), 1/2 | 413 (%54), 1/2 |

- **Yumuşak uyarılar:** Danza ve Toca'da gem payları rock şarkısının paylarından uzak (reggaeton'da kick ve snare çok, ride az). Uyarı veriyor, build'i durdurmuyor.
- **Risk, Toca Easy:** %84 snare, %2 kick. Toca'da bulunan neredeyse her kick'in yanında snare var (K+S+Hh 163 konum) ve Easy'de pad kick'i yeniyor. Easy her vuruşta tek snare'e dönüyor. Dembow ve dans davulunda doğrusu bilinmiyor, insan chart'ı yok. Proje sahibi çaldı: tekdüze gelmedi.
- Expert'te 37-40 ms arayla iki konum (flam) kalabiliyor: Danza'da en kısa aralık 0,08 vuruş. Bu C.1'den; alt seviyelerde aralık kuralı bunları ayırıyor.

**Gitar ve bas değişmedi.** Danza, Toca ve LastResort yeniden derlendi: `[SyncTrack]`, `[Events]`, bütün bas ve gitar bölümleri ve `[ExpertDrums]` C.1 sürümüyle bayt bayt aynı, yalnızca `[HardDrums]`, `[MediumDrums]`, `[EasyDrums]` eklendi. `song.ini` değişmedi. Üçü de validator'dan geçti.

**`evaluate`:** davulun alt seviyeleri insanla ve iki taban skoruyla ayrı satırlarda raporlanıyor (`drum_levels`). Expert'in satırları değişmedi.

**`analysis.json` ve terminal:** her davul seviyesinin ölçüleri (konum oranı, konum başına gem, vuruş üstü, 16'lık payı, en kısa aralık vuruş ve saniye olarak, gem payları), yumuşak hedefleri ve doğrulanmamış tom/crash sayıları. `drum_hard_rules` altı kural listeliyor.

**Oyun** (Clone Hero v1.0.0.4080-final):
- Danza, Toca ve `Davul Testi - LastResort` `Songs`'a kopyalandı (`notes.chart`, `song.ini`, `.ogg`'ler, `analysis.json`; `debug` yok). Önceki Danza ve Toca kopyaları scratchpad'e yedeklendi; yeni kopyalarda bas bölümleri ve `[SyncTrack]` onlarla aynı.
- Bot önizleme: üç şarkı da `--player ProDrums,<seviye>` ile dört seviyede açıldı, botlar çalıyor (ekrandaki seri sayacı artıyor; sayaç tek oyuncunun), log'da hata yok. `--player Drums` ile oyun cymbal'leri yuvarlak pad olarak gösteriyor, bu yüzden CLI artık önizleme komutunda `ProDrums` yazıyor.
- Bot isabet oranı ölçülmedi, insan henüz çalmadı.

**Klavyede davul: adım adım.** Ekranlar oyunda görüldü; atama yapılmadı, ayarların değişmedi.
1. **Tuş eşleme:** ana menüde **Space** → "Controller Remap". "Players" altında **Player1** seçili kalsın.
2. Davul tuşlarını **Keyboard'un ikinci (boş) sütununa** ata. Birinci sütundaki A S D F G gitarın; onlara dokunmazsan gitar aynen çalışır. Önerilen düzen (sağ el orta sıra, tom'lar üst sıra, kick sol işaret parmağı):

   | Satır ("Actions") | 2. sütun | Davulda |
   |---|---|---|
   | Orange | B | Kick |
   | Red | H | Kırmızı pad (snare) |
   | Yellow Cymbal | J | Sarı cymbal (hi-hat) |
   | Blue Cymbal | K | Mavi cymbal (ride) |
   | Green Cymbal | L | Yeşil cymbal (crash) |
   | Yellow | U | Sarı tom |
   | Blue | I | Mavi tom |
   | Green | O | Yeşil tom |

   Kullanma: **Space** (Open Button'a atanmış; kick'e de atanırsa gitarda open notalar bozulur), **;** (Keyboard Whammy), oklar, Right Shift (Start), Return (Select / Star Power). Kick'i Space'e almak istersen önce Space'i Open Button'dan kaldır. 2X Kick, Drum Pad Modifier, Drum Cymbal Modifier ve (auto)CymExt satırları boş kalabilir. Kutuya tıklayınca açılan atama penceresini açmadım; wiki'ye göre "Replace"e basıp tuşa basılıyor.
3. **Done** ile kapat.
4. **Profil:** ana menüde **Start** (sende Right Shift) → "Choose a Profile" → **Guest**'i A ile seç → **Start**'a yeniden bas → **Controller** → **Drums** ("5 Lane Compatibility" değil). Gitara dönerken aynı yerden "5 Fret Guitar". Lefty Flip kapalı kalsın.
5. **Şarkı:** Quickplay → şarkı → enstrüman **Pro Drums** → zorluk. Bu ekranı görmedim: wiki'ye göre Drums profilinde varsayılan Pro Drums; bot önizlemede şeridin adı "Pro Drums".
6. Önerilen sıra: önce `Davul Testi - LastResort` (gerçek davul seti, rock), sonra Danza ya da Toca; her birinde Easy ve Hard.

**Çalarken neye bakmalı:** kick ve snare zamanlaması, hi-hat'in sarı ve ride'ın mavi şeritte doğal gelip gelmediği, Easy'nin tekdüze olup olmadığı (özellikle Toca), Hard'daki 16'lıkların çalınabilirliği. Not için şarkı, seviye ve dakika:saniye yeterli.

**Değişen testler** (tolerans gevşetilmedi):
- `test_a_drum_stem_becomes_an_expert_drum_track`: artık dört seviye bekliyor (önce "alt seviyeler C.2'de" diye yalnızca Expert'i bekliyordu); alt seviyelerde `drum_chart` yok, hepsinde `drum_measures` var.
- `test_a_build_charts_drums_says_what_is_not_verified_and_writes_listening_files`: önce `[HardDrums]`'ın olmamasını istiyordu, artık dört bölümü istiyor; alt seviyelerin ölçü ve yumuşak hedeflerini ve altı davul kuralını da denetliyor.
- Yeni: `tests/test_drum_difficulty.py`.

**Kontroller:** `check.ps1 -Full` geçti: 927 test (839 + 88 yeni), 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti (yeniden derlenen Danza, Toca ve `Davul Testi - LastResort` dahil), gitar ve bas hash'leri ve onaylanan F1 alt sınırları dahil. Süre 900 sn: aynı anda Faz D için bir ölçüm betiği çalıştı; alt sınırlar eklenmeden önceki çalışma 555 sn sürmüştü. pytest'in tepe özel belleği 3,42 GB, çalışma kümesi 2,33 GB; makinenin en düşük boş RAM'i 4,3 GB (başta 6,2). Boş commit 1,1 GB'a kadar indi (hızlandırma ölçümlerinde en az 2,8 GB); pytest'in kendi belleği aynı kaldığı için büyük ihtimalle başka uygulamalardan.

## Test hızlandırma (C.1'den sonra, ayrı commit)

İstenen: aynı gerçek şarkının stem'leri ve tempo haritası oturumda bir kez hesaplansın ve paylaşılsın; Demucs modeli oturumda bir kez yüklensin, iş bitince bırakılsın; gerçek şarkı testleri ayrı bir işarete alınsın; `check.ps1`'e ara kademe eklensin, `-Full` yine hepsini çalıştırsın; pytest-xdist eklenmesin.

**Ne değişti:**
- **Yeni işaret `real`:** proje sahibinin şarkıları (`CHARTGEN_MUSIC_DIR`) ve referanslar (`CHARTGEN_REFERENCE_DIR`), 17 test. Önceden `slow` idiler. `slow` artık yalnızca sentetik seste gerçek Demucs çalıştıran 2 test. Varsayılan `pytest` ikisini de atlıyor.
- **`real_song` fixture'ı** (`tests/conftest.py`): şarkının sesi, stem'leri, mono analiz sinyalleri ve tempo haritası oturumda bir kez hesaplanıyor ve o şarkının testleri bunu paylaşıyor. Her şey testlerin kendi yaptığı gibi hesaplanıyor, diziler salt okunur. Aynı şarkının testleri art arda çalışıyor ve bir şarkı bırakılmadan sonraki yüklenmiyor; bellekte en fazla bir şarkı duruyor. Oturum sonunda terminal yükleme sayısını yazıyor (`real songs: 5 loaded, 5 loads, each once`). Pytest bunu kendisi yapamıyor, çünkü parametreleri değere göre değil listedeki sıraya göre grupluyor; sıralamayı conftest yapıyor.
- **Paylaşılmayanlar:** Danza ve Toca'nın uçtan uca build testleri ve `evaluate` testi kendi hesaplarını yapıyor, çünkü denedikleri şey tam boru hattı.
- **Demucs modeli** (`demucs_loaded_once`): üç ayrıştırma, bir yükleme (testte sınanıyor). Model, testlerin modülü bitince bırakılıyor. Yükleme 0,7-1,3 sn sürdüğü için kazanç yaklaşık 3 sn.
- **Sıra:** önce diğer testler, sonra şarkı şarkı gerçek şarkılar, en son gerçek Demucs. Torch bir model çalıştırdıktan sonra model bırakılsa da süreçte yaklaşık 1,4 GB tutuyor. Demucs testleri şarkılardan önce çalışınca pytest'in tepe özel belleği 4,42 GB'a çıktı, en sona alınınca 3,42 GB oldu.
- **`check.ps1 -Mid`:** gerçek şarkılar ve referanslar dışında her şey (822 test, yaklaşık 4,5 dk). Hızlı kademe `not slow and not heavy and not real` oldu, `-Full` yine hepsini çalıştırıyor.

**Önce ve sonra** (bu makine, 15,3 GB RAM, 2026-11-11):

| | Önce (`3029bc8`) | Sonra |
|---|---|---|
| `check.ps1 -Full` | 1229 sn | 564 sn |
| Aynı 19 test, art arda | 523 sn | 338 sn (sonraki çalışmada 307) |
| pytest tepe özel bellek | 3,24 GB | 3,42 GB |
| pytest tepe çalışma kümesi | 2,33 GB | 2,33 GB |
| Makinenin en düşük boş RAM'i | 3,40 GB (başta 5,6) | 5,02 GB (başta 7,4) |
| `check.ps1 -Mid` | – | 275 sn, tepe özel bellek 2,87 GB (Demucs testleri sona alınmadan önce ölçüldü) |

**Toplam süredeki düşüşün çoğu makine yükünden.** Değişmeyen 820 test aynı gün 547, 365 ve 253 sn sürdü. Değişikliğin kendi payı "art arda" satırında: eski testler `HEAD`'den çıkarılıp aynı kodla çalıştırıldı, hemen ardından yenileri. 19 testte −185 sn (%35). Tepe bellek 0,18 GB arttı: paylaşılan şarkı mono sinyallerini ve sesi testleri boyunca tutuyor.

**Kalan süre nerede:** gerçek şarkı testlerinde zamanın çoğu basın `librosa.pyin`'inde (Toca'da bas chart'ının 13,3 sn'sinin %98'i). Aynı şarkının bası oturumda birden çok kez chart'lanıyor: Toca ve Californication 3, Danza 2 (build ve `evaluate` testleri, hash testi, sınır testi). Bunu paylaşmak üretim koduna dokunmayı gerektirir; öneri olarak duruyor, uygulanmadı.

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

## C.1: Expert davul, kulak testi

**Nasıl duyuluyor** (`audio/drum_hits.py`, ayarlar `audio/drum_hits.toml`):
- Üç dedektör yan yana: kick 30-130 Hz, snare 150-600 Hz (ikisi doğrusal spektral akış), cymbal 7-11 kHz (desibel akışı; kapalı hi-hat ile crash arasındaki ses farkı doğrusal ölçekte hi-hat'leri gizler). 35 ms içindeki vuruşlar bir konum olur, aynı konumda birden çok parça olabilir.
- **Her eşik stem'in kendi güçlü vuruşlarına göreli:** dedektör, zirvelerinin yüksek bir yüzdelik dilimini (kick %99, snare %90, cymbal %95) "güçlü vuruş" sayar ve onun bir payına (0,5 / 0,1 / 0,25) ulaşan zirveleri alır. Vuruş sayısını sabitleyen eşik yok. Prototipin yüzdelik eşikleri kaldırıldı.
- **Sızıntı kuralları,** aynı anda iki bandı aynı spektrumdan karşılaştırır: snare bandı kick bandının en az 1,0 katı yükselmeli (kick'in gövdesi snare bandına taşar), kick bandı snare bandının en az 0,3 katı (snare'in gürültüsü aşağı taşar), cymbal'in yüksek bandı stem'in yüksek düzeyine (%95 RMS) en çok 48 dB uzak olmalı (başka davulun tıkı ya da gürültü tabanı log ölçekte cymbal gibi görünür).
- **Cymbal türü:** 90 ms içinde tepe seviyesinin %40'ının altına düşen hi-hat; kick'le gelen, cymbal'lerin güçlü vuruşunun en az 0,9'u kadar ve 0,6 sn sonra hâlâ %30 çınlayan crash; gerisi ride.
- **Tom:** gürültü bandı (2-5 kHz) gövdenin 0,3'ünün altında kalan snare-bandı vuruşu, perdesine göre yüksek, orta ya da yer tomu. Kick'le birlikte gelen ya da enerjisi kick bandında toplanan böyle bir vuruş kick'in kendi gövdesidir (808 gibi) ve atılır.
- Gecikmeler sentetik vuruşlarla ölçüldü: zarflar saldırıdan 1-7 ms önce tepe yapıyor, hiçbir şey çıkarılmıyor.

**Chart** (`chart/drum_charter.py`): vuruşlar gitarla aynı 16'lık ızgaraya oturur. Aynı tick'e düşenler birleşir: şerit başına bir gem (cymbal tom'u yener), en fazla 2 pad (önce snare, sonra güçlü cymbal, tom en son). Kesin kurallar kodda (`check_drum_track`) ve validator'da; `drum_hits.toml` bir konumun ne tutabileceğine karar veremez, öyle bir anahtar reddedilir. Davul yalnızca Expert'te; alt seviyeler C.2'de.

**NMF:** kullanılmadı. Göreli eşik kuralıyla doğrusal bant akışı kick'te NMF'yi geçti (Californication, ızgaradan önce: F1 0,962 / 0,952). NMF bu 324 sn'lik şarkıya yaklaşık 0,9 sn eklerdi (mel spektrogram + 60 yineleme; STFT ortak). Davul analizinin tamamı aynı şarkıda 1,4-1,8 sn; Danza, Toca ve LastResort build'lerinde 0,5-0,7 sn.

**Kabul kriterleri** (Californication, `train`, Expert, chart'a yazıldıktan sonra; ayarlar bu şarkıda seçildi, yani iyimser):

| Ölçüt | Hedef | Sonuç |
|---|---|---|
| Konum F1 | ≥ 0,85 | 0,919 (P 0,928, R 0,910) |
| Kick F1 | ≥ 0,80 | 0,962 |
| Snare F1 | ≥ 0,70 | 0,908 |
| Cymbal F1 | ≥ 0,80 | 0,874 (P 0,825, R 0,929) |
| Hi-hat ile ride'da doğru şerit | ≥ %75 | %78,9 (774 karşılaştırma) |
| En büyük gem payı sapması | ≤ 0,12 | 0,054 (mavi cymbal %31,3 / 25,9) |
| Aynı desen iki seviyede aynı vuruşlar | kesin | Sentetik kitte 1,0, 0,3 ve 0,05 seviyede birebir aynı |

Gem payları (ben / insan): kick %14,2 / 14,8, kırmızı %35,8 / 38,2, sarı cymbal %17,6 / 18,1, mavi cymbal %31,3 / 25,9, yeşil cymbal %1,1 / 2,1, sarı tom %0 / 0,8.

**`.sng` davul kanallarına karşı teşhis** (kabul kriteri değil): kanallar mikrofon kayıtları ve her biri diğer davulları da duyuyor; kick kanalında 661 onset var, insan 288 kick yazmış.

| Kanal | Onset | Bizim F1 | İnsanın F1'i |
|---|---|---|---|
| `drums_1` (kick) | 661 | 0,601 | 0,607 |
| `drums_2` (snare) | 1443 | 0,638 | 0,669 |
| `drums_3` (diğer) | 1257 | 0,773 | 0,740 |

Bizim chart kanallarla insanınki kadar örtüşüyor; kick ve snare'de kanalın yarısından azını ikimiz de yazıyoruz.

**Gerçeği olmayan şarkılar** (`--drum-ear-test` ile, `outputs\<şarkı>\debug\drums_*.wav`):

| | Konum | Kick | Kırmızı | Sarı / mavi / yeşil cymbal | Tom |
|---|---|---|---|---|---|
| Danza | 1073 | 463 | 598 | 614 / 215 / 9 | 6 yer tomu |
| Toca | 527 | 232 | 305 | 359 / 85 / 3 | 14 orta tom |
| LastResort | 765 | 344 | 310 | 199 / 305 / 8 | 0 |

Danza ve Toca yeniden derlendi (`--click-overlay --drum-ear-test`): bas bölümleri ve `[SyncTrack]`, oyundaki (`Songs`) çalınmış kopyalarla birebir aynı. LastResort için tempo testi klasörlerine dokunulmadı, yeni klasör `outputs\Davul Testi - LastResort`. `Songs`'a kopyalanmadı.

**Sentetik kit:** kick ve snare hiç karışmıyor; hi-hat %71, ride %75 (ikisi de kısmen kick, snare ya da çınlayan crash altında), yüksek ve orta tom tam, 808 kick'i tom değil kick. Dört kat yoğun kick deseninde de vuruşların hepsi bulunuyor.

**Sınırlar:**
- **Tom ve crash doğrulanmadı** (terminal ve `analysis.json`). Californication'da tom üretmiyoruz (insan 16 sarı tom yazmış, bu şarkıda gürültü ölçüsü ayıramıyor), crash'lerimizin çoğu insanın crash'iyle eşleşmiyor.
- **Yer tomu kaybolur:** 100 Hz'i kick bandında, gürültüsüz alçak vuruşlar kick gövdesi sayılıyor (`test_known_limit_a_floor_tom_is_lost`).
- **Hi-hat/ride eşiği dar bir tepe:** komşu ayarlar 0,74-0,78 veriyor, tek şarkıda seçildi.
- **Ride log ölçekte zayıf:** çınlaması sürerken gelen vuruş az yükseliyor; sentetik ride'ın %75'i bulunuyor.
- Kick'le birlikte vurulan snare'lerin bir kısmı kaybolabilir: Californication'daki 21'in 3'ü.

**Kulak testi: neye bakmalı.** Her dosya davul stem'i ve yalnızca bir parçanın tıkları (2,5 kHz, kısa). Bir dosyayı baştan sona dinle:
1. **Her tık o parçanın üstünde mi?** `drums_kick.wav`'da tık kick'le, `drums_snare.wav`'da snare'le aynı anda gelmeli. Başka bir şeyin üstüne düşen tık yanlış nota demek.
2. **Tıksız kalan vuruş var mı?** O parçayı duyduğun hâlde tık yoksa nota eksik.
3. **Hi-hat mı ride mı?** `drums_hihat.wav`'da tıklar kısa, kuru "çık"larda; `drums_ride.wav`'da uzun çınlayan "tiiing"lerde olmalı. Yer değiştirmiş olanları not et.
4. **Crash ve tom** doğrulanmadı: `drums_crash.wav`'da tıklar büyük patlamalarda (genelde bölüm başında), `drums_toms.wav`'da tonlu "dum"larda mı?
Not almak için dosya adı ve dakika:saniye yeterli; birkaç örnek yeter.

**Kontroller:** `check.ps1 -Full` geçti: 839 test (801 + 38 yeni), 1229 sn, 8 klasör validator'dan geçti (yeni `Davul Testi - LastResort` dahil), gitar ve bas hash'leri dahil. İlk deneme bellek yetmediği için yarıda kalmıştı; bu deneme, proje sahibi bellek kullanan uygulamaları kapattıktan sonra yapıldı.

| Bellek (`-Full`, 15,3 GB RAM) | Değer |
|---|---|
| pytest sürecinin tepe çalışma kümesi | 2,33 GB |
| pytest sürecinin tepe özel belleği | 3,24 GB |
| Makinenin en düşük boş RAM'i | 3,40 GB (başta 5,6 GB), `test_the_configured_limit_costs_the_human_bass_chart_at_most_0_005` sırasında |
| En düşük boş commit (5 sn'de bir örneklendi) | 2,8 GB |

Bellek sızmıyor: testler arasında pytest süreci 0,4-0,6 GB'a iniyor. Ölçüm, standart kütüphaneyle yazılmış geçici bir pytest eklentisiyle yapıldı (projede değil). Boş RAM 1,5 GB'ın altına düşse pytest'i kesip o anki testi yazacaktı; düşmedi.

**Değişen testler** (tolerans gevşetilmedi):
- `test_absent_stems_get_no_file_and_no_chart`: davul stem'i var ve artık chart'lanıyor, `diff_drums` -1 değil.
- `test_present_but_not_yet_charted_stems_keep_their_audio` kaldırıldı: chart'lanmayan enstrüman kalmadı. Yerine `test_present_stems_keep_their_audio_and_drums_are_charted`.
- `test_a_song_without_a_guitar_builds_on_its_bass`, `test_three_instruments_share_one_sync_track`: sentetik şarkının davulu (click) artık chart'lanıyor; ikincisi dört enstrümanın aynı `[SyncTrack]`'e oturduğunu da denetliyor.
- `test_no_instrument_to_play_stops_with_an_explanation_and_no_folder`, `test_with_nothing_to_play_the_build_still_stops`, `test_a_song_can_build_on_keys_alone`: davul stem'i de susturuldu, yoksa çalınabilir enstrüman kalıyordu.
- `test_real_songs_without_a_guitar_build` (`-Full`): Danza ve Toca'nın `diff_*`'ında artık davul da var.

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
- **Şarkı sözü (lyric olayları):** konuşma tanıma (Whisper gibi) ve sözlerin vokal notalarına hizalanması gerekir; yeni ve ağır bir bağımlılık. Proje sahibi 2026-11-11'de "yazma, ileride" dedi.
- **Testlerde `pyin` paylaşımı:** gerçek şarkı testlerinde zamanın çoğu basın `librosa.pyin`'inde, aynı şarkının bası oturumda 2-3 kez chart'lanıyor (Toca ve Californication 3, Danza 2). Paylaşmak üretim koduna dokunmayı gerektirir. Proje sahibi 2026-11-11'de "şimdilik uygulama" dedi.

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
| C.0 | Davul formatı (4-lane Pro), yazıcı, validator, referans okuyucu, bas hash'leri | `1fd3d91` |
| C.1 | Expert davul: sınıflandırma, chart, `evaluate`, kanal teşhisi, `--drum-ear-test` | `3029bc8` |
| Test hızlandırma | Gerçek şarkı oturumda bir kez, Demucs modeli bir kez, `real` işareti, `check.ps1 -Mid` | `dd05eb0` |
| C.2 | Davul Hard, Medium, Easy, `evaluate` seviyeleri, `ProDrums` önizleme; Faz C kapandı | `1ec287d` |
| D.0 | Bölüm, star power ve preview ölçümü (insan chart'ından), `evaluate` yapı satırları | `7251c84` |

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

Pre-commit hook 39–80 sn sürüyor (hızlı testler + validator, makine yüküne göre değişiyor). `-Full` B3.3'te 642 sn idi. 2026-11-10'da değişmemiş `2e91ece` 957 sn, C.0 koduyla 1031 sn sürdü: C.0'ın yeni testleri yaklaşık 75 sn ekliyor, gerisi büyük ihtimalle makine yükü (ölçülmedi). C.1 koduyla 1229 sn (839 test, 2026-11-11). En uzun 8 testin hepsi gerçek şarkı ya da referans testi, toplam 535 sn. Test hızlandırmadan sonra 564 sn, `-Mid` 275 sn ("Test hızlandırma" bölümüne bak).

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
- **Davul tek referanstan:** sınıflandırıcının eşikleri ve alt seviyelerin oranları Californication'dan (rock). Tom ve crash doğrulanmadı (build bunu yazıyor). Danza ve Toca'da gem payı uyarıları, hedef paylar rock şarkısından geldiği için; oynarken sorun görülmedi.
- **Davul Expert'te flam:** 37-40 ms arayla iki konum kalabiliyor (C.1'in 35 ms birleştirme sınırının hemen üstü). Alt seviyelerde aralık kuralı bunları ayırıyor.

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
