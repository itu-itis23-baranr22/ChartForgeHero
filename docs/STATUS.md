# Proje durumu

A'dan D'ye bütün fazlar tamamlandı. Yeni insan chart'larıyla ayar (0-5. adımlar, aşağıda "Referanslarla ayar") ve ardından "sonra" listesi kapandı: Sonra 1 bölümler (`a28d9fd`), Sonra 2 star power (`f26b54f`); Sonra 3 preview P1 uygulanmadı, kodu `preview-p1` branch'inde (`11ef55d`), main'de D.2 preview'u kalıyor. Sıradaki iş proje sahibinin "Yapılacak / kontrol edilecek" listesinden seçtiği. Şartname ve alınan kararlar `docs/SPEC.md` dosyasında.

## Şu anki adım

**Referanslarla ayar, 5. adım (alt seviye oranları; hızlı şarkıda Easy davul): kapandı (SPEC 45).** 5a gitar Hard oranı 0,80; 5b bas Medium'da dörtlük her zaman kalabilir ve oran 0,50 (bas Hard değişmedi); 5c R1. **Proje sahibi 2026-11-16'da onayladı:** Californication'daki iki kötüleşme kabul (gitar Hard P düştü ama F1 yükseldi; sustain farkı küçük), beş gerçek şarkı hash'i ve iki dosya hash'i onaylı, bas Hard'ın değişmemesi doğru; gitar Hard'daki sınırlı kazanç ve 1981'in Easy davulu açık konu olarak kalıyor. `-Mid` (hızlı kademe dahil) 1081 test 449 sn geçti; `-Full` proje sahibinin penceresinde geçti (2026-11-16: 1102 test, 1347 sn, makine yüklüydü; 9 klasör validator'dan geçti); commit edildi (`4643b4c`). Ardından altı şarkı (Davul Testi - LastResort, Şarkı Testi, Zombiler, Danza, Toca, Tempo Test - LastResort otomatik) 5. adımın koduyla derlenip `Songs`'a ve `outputs\`'a kopyalandı (oyun kapalıyken; öncekiler `outputs\_songs_backup\2026-11-16_adim5\`; derlemeler `outputs\_experiments\adim5_seviye\derlemeler_sonra\`, Şarkı Testi'nin `debug_click.wav`'ı eski kopyadan, tempo haritası aynı); dosya kümeleri aynı, altısı da `Songs`'ta validator'dan geçti. **Oyun testi onaylandı (proje sahibi, 2026-11-16):** Zombiler davul Easy'de kick-snare yorgunluğu gitti, rahat çalınıyor; Zombiler ve LastResort bas Medium'un yoğunluğu iyi; Danza ve Toca bas Medium hâlâ iyi, **5b kalıyor (geri alma seçeneği kapandı)**; LastResort gitar Hard Expert'ten yeterince farklı, sıkışan yer yok. Sıradaki: "sonra" listesi; **Sonra 1, bölümler: kapandı (SPEC 46).** 150 BPM üstünde bölüm aramasında ölçüler ilk sesli ölçüden ikişer ikişer alınıyor (B2). `-Mid` (hızlı kademe dahil) 1084 test, 433 sn geçti (`outputs\` artık 10 klasör: proje sahibinin kendi derlediği `Mor ve Ötesi - Bir Derdim Var` da var, validator'dan geçiyor); `-Full` proje sahibinin penceresinde geçti (2026-11-16: 1105 test, 820 sn, 10 klasör). **Proje sahibi 2026-11-16'da onayladı:** B2 (ilk sesli ölçüden çiftleme) ve artımlı tablo (yapay iki kat tempo sonucu ikna edici); test setinde Kids (−0,044) ve 1981'in (−0,173) düşüşü kabul, 1981'in kısa bölümleri açık konu; LastResort ve Zombiler'in yeni bölümleri ve preview noktaları onaylı. Commit edildi (`a28d9fd`). Ardından Songs'ta LastResort, Zombiler ve Tempo Test - LastResort otomatik güncellendi (oyun kapalıyken; yalnızca bölümler ve preview değişti; öncekiler `outputs\_songs_backup\2026-11-16_bolumler\`; üçü de validator'dan geçti; `outputs\`'taki kopyalar da aynı). **Sonra 2, star power aralığı: kapandı (SPEC 47).** İfadeler ölçüyle: ilki şarkı başından 9 ölçü sonra, sonrakiler ~10 ölçü arayla (7-13). `-Mid` (hızlı kademe dahil) 1087 test, 334 sn, 10 klasör geçti; Californication star power testi (`real`) yeni şartla geçti. **Proje sahibi 2026-11-16'da onayladı:** artımlı tablo, Californication star power testinin ölçüyle yazılması; hızlı şarkılardaki fazla ifade (test setinde 1981, gerçek dışı Zombiler ve LastResort dakikada 4,5-4,9) açık konu. `-Full` proje sahibinin penceresinde geçti (2026-11-16: 1108 test, 1102 sn, 10 klasör validator'dan geçti); commit edildi (`f26b54f`). Ardından yedi şarkı (Davul Testi - LastResort, Danza, Toca, Mor ve Ötesi, Zombiler, Tempo Test - LastResort otomatik, Şarkı Testi) `Songs`'a ve `outputs\`'a kopyalandı (oyun kapalıyken; derlemeler `outputs\_experiments\adim7_starpower\derlemeler_sonra\`, commit'lenen kodla aynı hash'li kodun çıktısı; öncekiler `outputs\_songs_backup\2026-11-16_starpower\`): `Songs`'taki dosya kümeleri aynı (tıklama dosyaları yerinde; Mor ve Ötesi'nde `debug` yok), `.ogg`'ler örnek örnek aynı, `song.ini`'ler bayt bayt aynı; yedisi de `Songs`'ta ve `outputs\`'ta validator'dan geçti. **Sonra 3, preview P1: uygulanmadı (proje sahibinin kararı, 2026-11-16); eski sistem (D.2, SPEC 39) kalıyor.** Kod, testler ve belgeler `preview-p1` branch'inde (`11ef55d`, main'e alınmadı, `-Full` çalışmadı); `Songs`'a dinlemek için kopyalanan `song.ini` ve `analysis.json`'lar yedekten (`outputs\_songs_backup\2026-11-16_preview\`) geri konuldu, yedisi validator'dan geçti, `outputs\`'takilerle aynı. Ayrıntı: aşağıda "Sonra 3". **Sıradaki: proje sahibi aşağıdaki "Yapılacak / kontrol edilecek" listesinden seçecek.** Ayrıntı: aşağıda "Sonra 2". Ayrıntı: aşağıda "Sonra 1: bölümler". Ayrıntı: "Referanslarla ayar" bölümünde 5. adım.

**Referanslarla ayar, 4. adım (davul) kapandı (SPEC 44, B seçeneği).** `-Full` proje sahibinin penceresinde geçti (2026-11-16: 1093 test, 688 sn, 9 klasör validator'dan geçti); commit edildi (`d1de7f0`). Ardından davullu beş şarkı (Davul Testi - LastResort, Şarkı Testi, Zombiler, Danza, Toca) güncel kodla yeniden derlenip `Songs`'a kopyalandı (oyun kapalıyken; öncekiler `outputs\_songs_backup\2026-11-16_adim4\`): yalnızca davul bölümleri değişti, `[SyncTrack]`, `[Events]`, gitar, bas ve `song.ini` aynı, `.ogg`'ler örnek örnek aynı (baytları yalnızca Ogg akış numarasında farklı); beşi de `Songs`'ta validator'dan geçti. `Tempo Test - LastResort otomatik` (yalnızca gitar) ve `SP Deneyi - Davul` değişmedi. Derleme günlüğü `outputs\_experiments\adim4_davul\songs_derleme.log`. **Bekleyen:** 5. adımın planı sunuldu (aşağıda 4. adımdan sonra), proje sahibinin onayı. 3. adım `29419df`'te kapandı; ardından altı şarkı (Zombiler, iki LastResort klasörü, Şarkı Testi, Danza, Toca) o kodla yeniden derlenip bütün klasörleriyle `Songs`'a kopyalandı, hepsi validator'dan geçti; öncekiler `outputs\_songs_backup\2026-11-15_adim3\`.

**2. adımın `-Full`'u (2026-11-15):** proje sahibinin kendi PowerShell penceresinde geçti: 1045 test, 657 sn, 9 klasör validator'dan geçti. Üç sabit test değeri proje sahibinin onayıyla güncellendi.

1. adımın notları: Proje sahibi LastResort'u kulakla ~181 buldu (eşik %65'te kalıyor); sustain artışı 3. adıma bırakıldı, 3. adıma kadar `Songs`'a hiçbir şey kopyalanmıyor. LastResort'un üç sabit test değeri proje sahibinin onayıyla güncellendi.

**`-Full` (2026-11-15):** proje sahibinin kendi PowerShell penceresinde geçti: 1039 test, 633 sn, 9 klasör validator'dan geçti.

Önceki durum: Faz D `c322249`'da kapandı (D.3, star power).

**`-Full` (2026-11-15):** proje sahibinin kendi PowerShell penceresinde geçti: 1022 test, 600 sn (check 605 sn), 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti (yeniden derlenen dört şarkı star power'lı). Californication star power testi, gitar ve bas hash'leri, davul F1 alt sınırları ve gerçek Demucs testleri dahil. Bu koşuda tepe bellek ölçülmedi.

## Yapılacak / kontrol edilecek

Proje sahibinin listesi (2026-11-16). Sıra ve kapsam proje sahibinin kararı; her biri ayrı adım olarak planlanır.

- **Preview P1** (branch `preview-p1`, `11ef55d`): `train` iyileşti (nakarat isabeti 6/8 → 7/8, insan preview'una ortanca uzaklık 34 → 17 sn), test seti kötüleşti (nakarat 2/4 → 1/4, Kids girişe kaydı: 16 ölçü 199 BPM'de ~19 sn). Hızlı şarkılar için 150 BPM tabanı fikri (başa yakınlık eşiğini saniyece 150 BPM'dekinden kısa saymamak; SPEC 41 gibi). Test seti bu sorunu gösterdiği için o düzeltmeyi doğrulayamaz. Karar verilmeden önce yeniden değerlendirilecek. Ayrıntı: aşağıda "Sonra 3" ve branch'teki STATUS.
- **LastResort'un insan yapımı chart'ı** (proje sahibi indirdi: `C:\Users\Rtbn7\Downloads\Papa Roach - Last Resort (Harmonix).sng`, 13,3 MB, 2026-11-16; `references\`'a kopyalanmayacak, `train\` ya da `test\` altına girmeyecek): ayrı bir ek kontrol olarak karşılaştırılacak: BPM (bizde ~181), preview, gitar, bas ve davul, bölümler. **Test setine katılmayacak**, `train`'e de değil: ayarlar ona göre yapılmaz.
- **Hızlı şarkılarda fazla star power:** Zombiler 16-17, LastResort 15-16 ifade (dakikada 4,5-4,9, yumuşak hedefin üstü); test setinde 1981 10-11 (insan 7-8), Kids 15-16 (insan 13-14). Ayrıntı: "Sonra 2".
- **1981'in kısa bölümleri** (insan ~8 ölçülük, ~10 sn bölümler; çiftlenmiş pencere görmüyor; "Sonra 1") **ve Easy davulu** (R1 1981'de insandan uzaklaştırdı; 5. adım); **gitar Hard'daki sınırlı kazanç** (`train` F1 0,703 → 0,718, hedef belirgin artıştı; 5. adım).
- **Daha önceki açık konular ve "ileride" listesi:** tom'lar ve crash (davulda doğrulanmadı); davul star power'ının oyunda açılışı (`SP Deneyi - Davul`, D.3'teki kontrol listesi); web editörü; şarkı sözü; basta open note (`N 7`); keys doğrulaması (piyanosu baskın bir şarkıyla). Öteki maddeler: aşağıda "İleride (özet)" (`pyin` paylaşımı, üretimde `OPENBLAS_NUM_THREADS`, FFmpeg Ogg yedek çözücüsü) ve "Bilinen sınırlar ve açık konular".

## Projenin genel durumu (2026-11-15)

**Ne yapıyor:** proje sahibinin kendi ses dosyasından Clone Hero şarkı klasörü üretiyor (`chartgen build`): Demucs ile stem ayrıştırma (önbellekli, sabit seed), değişken tempo haritası ve ölçü, şarkıya ait olmayan girişin ayıklanması, dört seviyede gitar, bas, keys ve 4-lane Pro Drums, bölümler, preview noktası, star power, `song.ini`, ayrı ses dosyaları (`vocals.ogg` dahil), her build'de validator ve her kararın gerekçesiyle `analysis.json`. Ayrıca `chartgen validate` ve insan chart'larıyla karşılaştıran `chartgen evaluate`.

**Enstrümanlar:**

| | Durum | Oyunda | Ölçüm (Californication, `train`) |
|---|---|---|---|
| Gitar | Dört seviye | Proje sahibi LastResort ve Şarkı Testi'ni çaldı | Expert nota F1 0,794; alt seviyeler "önce vuruşlar" tabanını geçiyor |
| Bas | Dört seviye, ayrı ayarlar | Danza ve Toca çalındı | Onaylı alt sınırlar testte; dört şarkının bası hash'le sabit |
| Pro Drums | Dört seviye, zil/tom | LastResort, Danza, Toca Easy ve Hard çalındı | Expert konum F1 0,919; seviye alt sınırları 0,85/0,85/0,80 testte; tom ve crash doğrulanmadı |
| Keys | Dört seviye | Hiçbir şarkıda piyano stem'i yok | Gerçek veriyle doğrulanmadı |
| Vokal | Yalnızca `vocals.ogg` | Ses kaydırıcısı çalışıyor | Şarkı sözü yok |

**Yapı (Faz D):** bölümler yapısal harflerle (`A1`, `B1`, `A2`; Californication sınır F1 0,750, eşik 0,70); preview tekrar eden en gürültülü bölümün ikinci başlangıcından 4 ölçü önce (insanınkinden 0,18 sn; kriter en çok 1 ölçü); star power her enstrümanda 1 ölçülük ifadeler, ilki 9 ölçü sonra, sonrakiler ~10 ölçü arayla (7-13; Sonra 2, SPEC 47), dört seviyede aynı yerde. Davulda star power'ın oyunda nasıl açıldığı doğrulanmadı.

**Güvence:** kesin kurallar kodda ve validator'da, yumuşak hedefler `.toml` dosyalarında (uyarır, build'i durdurmaz). `scripts\check.ps1`: hızlı kademe her commit'te (hook, ~1 dk), `-Mid` gerçek şarkılar olmadan, `-Full` her şey (gerçek Demucs, beş gerçek şarkı, referans; ~12 dk). `-Full`'da gerçek bir şarkı ya da referans dosyası eksikse testleri atlanıyor ama koşu hata koduyla bitiyor ve eksik dosyalar "real files missing" başlığı altında listeleniyor (`--require-real-files`, 2026-11-24); hızlı kademe ve `-Mid` gerçek testleri hiç seçmediği için etkilenmiyor. Testler `OPENBLAS_NUM_THREADS=4` ile çalışıyor. `-Full` proje sahibinin kendi PowerShell penceresinde çalıştırılıyor: Claude Code arka planda bellek azalınca onu durduruyor.

**Oyundaki şarkılar** (`Documents\Clone Hero\Songs`, 2026-11-24'te kontrol edildi): `Don Omar - Danza Kuduro`, `Fly Project - Toca Toca`, `Davul Testi - LastResort`, `Yerel Test - Şarkı Testi`, `Second - Zombiler`, `Mor ve Ötesi - Bir Derdim Var`, `Tempo Test - LastResort otomatik` (gitar tempo testi): bu yedisi star power koduyla (`f26b54f`, Sonra 2) 2026-11-16'da derlendi; preview'ları D.2'nin (P1 denemesinden sonra yedekten geri konuldu; 2026-11-24'te `song.ini` ve `analysis.json`'lar yedekle ve `outputs\` ile bayt bayt aynı). `SP Deneyi - Davul` (davul star power deneyi, 2026-11-15). Önceki kopyalar `outputs\_songs_backup\<tarih>\` altında.

**Sınır:** D fazına kadarki ayarlar tek insan chart'ından (Californication). 2026-11-15'ten beri 12 referans var (8 `train`, 4 `test`); ayarlar yalnızca `train`'de yapılıyor. Ayrıntı: "Referanslarla ayar" ve "Bilinen sınırlar ve açık konular".

## İleride (özet)

Proje sahibinin "şimdilik değil" dedikleri ve önerilip uygulanmayanlar. Ayrıntılar ilgili bölümlerde.

- **Web editörü** (proje sahibinin ilk planındaki Phase 5): timeline, ses senkronu ve notaları elle düzeltme. Başlanmadı.
- **Davul star power'ının oyunda açılışı** (proje sahibi test edecek): deney `outputs\_experiments\d3_sp_deneyi\` altında ve oyunda (`SP Deneyi - Davul`), kontrol listesi D.3 bölümünde. Sonuca göre `S 64` fill yazılıp yazılmayacağına karar verilecek.
- **Basta open note (`N 7`)** tekrar eden en alçak notalar için (proje sahibinin önerisi).
- **Şarkı sözü:** konuşma tanıma ve hizalama, yeni ve ağır bağımlılık.
- **Testlerde `pyin` paylaşımı:** gerçek şarkı testlerinin zamanının çoğu; üretim koduna dokunur.
- **Üretim build'inde `OPENBLAS_NUM_THREADS=4`:** build'in commit payını ~0,75 GB düşürür, çıktı aynı; önce süre ve tepe bellek ölçülmeli.
- **Keys doğrulaması:** piyanosu baskın bir şarkıyla oyunda ve `evaluate`'te.
- **FFmpeg kaynaklı Ogg dosyaları için ses yükleyicide yedek çözüm** (proje sahibinin isteği, 2026-11-15, uygulanmadı): libsndfile 1.2.2, FFmpeg (Lavf60) ile kodlanmış bazı Opus dosyalarını "malformed" diye reddediyor. Dosyalar sağlam (bütün Ogg sayfalarının CRC'si doğru); birkaç sayfanın granülü içindeki paketlerin süresiyle en çok 10 ms tutmuyor, hata birikmiyor. Üç referansta görüldü (Green Day - 1981, Green Day - Holiday, Sum 41 - Fat Lip); kopyalarında granüller paketlerden yeniden yazıldı, ses paketlerine dokunulmadı. Kullanıcının kendi `.ogg`/`.opus` girdilerinde de aynı sorun çıkabilir: yükleyici bu hatada granülleri bellekte düzelterek ya da başka bir çözücüyle (yeni bağımlılık, önce sürüm ve gerekçe) yeniden denemeli.

## Önceki adımlardan notlar

**Proje sahibinin kararları (2026-11-15, ikinci tur):** `OPENBLAS_NUM_THREADS=4` yalnızca test ortamına (`check.ps1`) eklendi; üretim build'i için ayrı öneri (aşağıda), uygulanmadı. Commit taslağı ve deney klasörü Temp'ten `outputs\_drafts\` ve `outputs\_experiments\` altına taşındı; `check.ps1` adı `_` ile başlayan klasörleri şarkı saymıyor. Deneyden önce davul star power tuşu denetlendi (D.3 hazırlığı).

**D.2 `-Full` (2026-11-15):** proje sahibinin kendi PowerShell penceresinde geçti: 992 test, 745 sn (check 750 sn), 5 gerçek şarkının her biri bir kez yüklendi, 8 klasör validator'dan geçti. Bu koşuda tepe bellek ölçülmedi. Claude Code'un arka planda başlattığı iki `-Full`'u Claude Code bellek azalınca durdurmuştu (aşağıda "Bellek"); bu yüzden `-Full` artık proje sahibinin penceresinde çalışıyor.

**Proje sahibinin D.2 kararları (2026-11-15):** dört şarkıda da preview tanınır kısma giriyor. Harf eşiği 0,6'da kalıyor. Preview kabul kriteri: Californication'da insanınkinden en çok 1 ölçü uzakta (teste yazıldı: insan chart'ının, insan preview'unun düştüğü ölçüsü; SPEC 39). D.1 commit mesajındaki küçük yanlışlık düzeltilmiyor, geçmişe dokunulmuyor.

D.1 `838c88a`'da kapandı (bölüm tespiti; proje sahibi 2026-11-12'de onayladı).

D.0 `7251c84`'te kapandı (ölçüm altyapısı; vokal paketlemesi proje sahibince oyunda doğrulandı).

Faz C `1ec287d`'de kapandı (C.2: davul Hard, Medium ve Easy). Proje sahibi 2026-11-11'de C.2'yi onayladı ve LastResort, Danza ve Toca'nın Pro Drums'ını Easy ve Hard'da çaldı: hepsi çalınabilir, hi-hat ve ride şeritleri doğal, Toca Easy tekdüze gelmedi, sorun yok. F1 alt sınırlarını onayladı (testte). `pyin` paylaşımı "ileride" listesinde.

Test hızlandırma `dd05eb0`'da kapandı. C.1 `3029bc8`'de kapandı (Expert davul chart'ı ve kulak testi dosyaları). Proje sahibi 2026-11-11'de C.2'ye geçilmesini istedi; kulak testinin sonucu henüz gelmedi. C.0 `1fd3d91`'de kapandı. Commit mesajlarına Claude imzası eklenmiyor: `.claude/settings.json` (`00681d2`).

B3 bitti (`2e91ece`): bas ve keys chart'lanıyor, şarkının gitara ihtiyacı yok.

Proje sahibi Danza'nın güncel bas Hard'ını çaldı: ritim rahat, sekizlik notalar doğal geliyor, sıkışıklık yok.

Proje sahibi Danza'nın bas Expert'ini çaldı: senkron iyi, 37-38 sn'deki hayalet notalar rahatsız etmiyor. Seviye kuralı kapalı kalıyor.

Proje sahibi Toca'nın bas Easy ve Hard'ını çaldı: vuruşlar ve zamanlama iyi, tekdüzelik rahatsız etmiyor, turuncu doğal geliyor. "Turuncu = tek perde" uyarısı yumuşak kalıyor: reggaeton'da tekrarlı bas için bu doğal.

## Referanslarla ayar (2026-11-15)

**Referanslar.** Proje sahibi `Desktop\clone hero songs`'a 11 `.sng` koydu (orijinallere hiç yazılmadı). 8'i okunuyordu. Üçünün (Green Day - 1981, Green Day - Holiday, Sum 41 - Fat Lip) Opus sesini libsndfile reddediyordu: dosyalar sağlam, birkaç Ogg sayfasının granülü paketlerle en çok 10 ms tutmuyor. Proje sahibinin onayıyla yalnızca kopyalarında granüller paketlerden yeniden yazıldı (ses paketleri aynı; okunabilen baş kısımlar örnek örnek aynı çözülüyor). Bölme (onaylandı): `train` Californication, Scar Tissue, Parallel Universe, Dani California, First Date, In Too Deep, Holiday, Fat Lip; `test` Otherside, The Kids Aren't Alright, We Will Rock You, 1981. Parallel Universe'ün davulu okunmuyor (disco flip), Fat Lip'te yalnızca Expert var, We Will Rock You'da bas ve davul dört seviyede aynı. `references\` git dışında.

**Ayarsız ölçüm** (mevcut kodla, 1118 sn): `outputs\_experiments\referans_degerlendirme_2026-11-15\` (`report.json`, gruplu tablolar `ozet.md`, teşhis betikleri). Özet: tempo oktav hatası (160 BPM üstü üç şarkı yarı tempoda), gitar Expert recall'ı düşük (`train` 0,54; kaçırılan notaların hepsinde zarf tepesi var, onları uyarlamalı eşik ve vokal süzgeci eliyor), turuncu neredeyse yok (`register_span` ve `lane_shares` Californication'dan), sustain fazla, davulda mavi zil fazla ve crash yok, Easy'de kick+hi-hat konumunda kick kalıyor, bas Hard ve Medium seyrek.

**Plan (proje sahibi onayladı, 2026-11-15):** 0. referans testi yalnızca Californication; 1. tempo oktavı ve ölçü fazı; 2. gitar Expert recall'ı (eşik ve vokal süzgeci); 3. gitar şerit dağılımı ve sustain; 4. davul (Easy/Medium gem seçimi, hi-hat/ride, crash); 5. alt seviye oranları (gitar Hard; bas yalnızca Hard ve Medium, bas Expert'e dokunulmaz; proje sahibi Danza ve Toca'yı tekrar çalacak, beğenmezse geri alınır). Sonra (5. adımdan sonra, birlikte): **öncelikli** bölümler, çünkü 1. adımdan beri hızlı şarkılarda fazla bölüyor (Kids 10 insan bölümüne karşı 31; proje sahibi: en kısa bölüm ve pencere uzunluğu ölçü yerine saniyeyle ya da 150 BPM ilkesiyle sınırlanmalı); star power aralığı (insan ~8-10 ölçü); preview. Kurallar: ayar yalnızca `train`'de; test her adımın sonunda, ayarlar dondurulduktan sonra bir kez ölçülür, gördükten sonra o adımda değişiklik yok; mevcut test alt sınırları kesin, başka bir Californication metriği 0,02'den fazla düşerse önce sorulur; asıl hedef `train` ortalamasının, özellikle RHCP dışının yükselmesi. Raporlar: `train` hepsi / RHCP / RHCP dışı, test hepsi / Queen ve 1981 hariç, ortalama ve medyan.

**0. adım:** `test_real_references_when_available` artık yalnızca Californication'ı değerlendiriyor (geçici bir `train\` klasörüne bağlı kopya; stem önbelleği içerikle anahtarlı). Önceden bütün `references\`'ı değerlendiriyor ve Californication'a göre konmuş bas alt sınırlarını her bölmede arıyordu. Tek başına 103 sn'de geçti.

**1. adım: tempo oktavı ve ölçü fazı** (SPEC 41).
- Tempo araması 160 BPM'de duruyor; daha hızlı şarkı önce yarı tempoda bulunuyor. Sonra snare karar veriyor (`audio/meter.py`, `check_double_time`): davul sınıflandırıcısının snare'leri sekizlik ızgaraya konuyor, 8 vuruşluk pencerelerde snare'in hem tek hem çift vuruşlara düşüp düşmediği sayılıyor. Doğru tempoda backbeat tek pariteye düşer (2 ve 4), yarı tempoda her vuruşa. Vuruş ikiye bölünüyor: pencerelerin en az %65'i iki paritede, en az 8 pencere, snare'lerin en çok %60'ı kick'le birlikte (fazlası kick'in snare bandına sızması, Toca gibi), bölünmüş tempo en çok 230 BPM. `--bpm` hiç bölünmüyor. Eski vuruşların hepsi ızgarada kalıyor; ölçü fazını bölünmüş haritada `detect_meter` buluyor.
- Ölçüm (bugünkü haritayla, "iki paritede" payı): doğru tempolu 6 `train` şarkısı 0-0,12, Fat Lip 0,48; First Date (insan 191, bulunan 95,6) 0,83; Zombiler (proje sahibi ~183 duyuyor) 0,86; LastResort 0,70; Şarkı Testi 0,50; Toca 1,0 ama snare'lerin %74'ü kick'le (ve 252 BPM tavanın üstünde). Betikler `outputs\_experiments\adim1_tempo\`.
- **150 BPM alt sınırı** (`core/timing.py`, `FLOOR_BPM`, `seconds_floor`): vuruşla sayılan bir kural, 150 BPM'deki süresinden azına izin vermiyor. Davul seviyelerinde aralık (`min_gap_s`: Hard 0,10, Medium 0,20, Easy 0,20 sn; `train` insanlarının hepsinin altında), Expert sustain (`MIN_SUSTAIN_S` 0,30 sn) ve seviyelerin sustain eşiği. Bunlar olmadan bölünmüş tempo Easy davula sekizlik sokuyor, First Date'in gitar Expert sustain'i %18'den %46'ya çıkıyordu (insan %1). 150 BPM ve altında hiçbir şey değişmiyor. Bas Hard'ın aralık kuralına dokunulmadı: o zaten "0,25 sn ya da yarım vuruş" (B3.2 kararı) ve First Date'in insan bas Hard'ı sekizlikleri tutuyor.
- **`train` sonucu** (`train_karsilastirma.md`): yalnızca First Date değişti, diğer 7 şarkı birebir aynı. First Date: 191,2 BPM; beats <35 ms 0,49 → 0,98; bars 0,00 → 1,00; ölçü güveni -0,33 → 8,72; davul konum F1 0,848 → 0,873 (Hard 0,816 → 0,830, Medium 0,869 → 0,876, Easy 0,867 → 0,873); bas Hard 0,687 → 0,772, Easy 0,135 → 0,811; gitar F1 aynı (0,534; recall 2. adımda); gitar sustain Expert %18 → %24 (insan %1), Easy %39 → %48; bölüm F1 0,583 → 0,538; preview 44 → 100 sn uzak. RHCP dışı bars agree ortalaması 0,62 → 0,87, medyanı 0,74 → 1,00.
- **Proje sahibinin şarkıları** (`derlemeler\`): Danza, Toca ve Şarkı Testi'nin `notes.chart`'ı ve `song.ini`'si `Songs`'taki hâlleriyle bayt bayt aynı. Zombiler 91,6 → 183,2 BPM (ölçü güveni 1,02 → 1,89), gitar otomatik HOPO %14 → %0, davul Easy en kısa aralık 0,25 sn. LastResort 90,6 → 181,1 BPM (ölçü güveni 1,9 → 12,1, bölümlerin %100'ü aynı fazı seçiyor), gitar otomatik HOPO %16 → %0; ama gitar sustain Expert %23 → %40, Easy %19 → %74 (Zombiler Easy %21 → %35): yarı tempo sustain eşiklerini saniyede iki kat uzun tutuyor ve distortion çınlamasını sustain sanma hatasını örtüyordu (3. adımın konusu).
- **Ek bulgu (2. adım için):** Zombiler'de vokal süzgeci gitarın 490 notasını siliyor (eski derleme; yenide 482). Gitar Expert'in 254 konumda kalmasının ana nedeni bu. Proje sahibinin kararı: 2. adımın öncelikli konusu, Zombiler orada gerçek dışı örnek olarak raporlanır.
- **Proje sahibinin kararları (2026-11-15):** LastResort'un bugünkü click'inde trampet her click'te geliyor, yani ~181 doğru; eşik %65'te kalıyor. Şarkı Testi dinlenmedi. Sustain artışı 3. adımda, geçici çözüm yok; 3. adıma kadar `Songs`'a hiçbir şey kopyalanmıyor.
- **Test seti** (ayarlar dondurulduktan sonra bir kez; `test_karsilastirma.md`): 1981 185,0 BPM (insan 185,0), Kids 199,5 (199,3), ikisinde de "iki paritede" payı 1,0; Otherside ve We Will Rock You bölünmedi, değişmedi. Önce → sonra, ortalama/medyan, test hepsi | Queen ve 1981 hariç: bars agree 0,49/0,49 → 0,96/0,96 | 0,50 → 0,94; beats <35 ms 0,68/0,65 → 0,92/0,94 | 0,71 → 0,94; gitar Expert F1 0,586/0,605 → 0,578/0,588 | 0,714 → 0,702; gitar Easy F1 0,284/0,243 → 0,381/0,438 | 0,409 → 0,575; bas Expert F1 0,737/0,818 → 0,719/0,792 | 0,818 → 0,804; bas Easy F1 0,353/0,389 → 0,549/0,589 | 0,318 → 0,653; davul Expert konum F1 0,798/0,866 → 0,794/0,858 | 0,888 → 0,888; davul Easy 0,806/0,846 → 0,818/0,857 | 0,846 → 0,857; bölüm F1 0,468/0,457 → 0,433/0,507 | 0,658 → 0,513 (Kids 0,778 → 0,488: 10 insan bölümüne karşı 31); gitar Expert sustain payı 0,20/0,19 → 0,26/0,30.
- **Yan etki, nedeni bulundu, 1. adımda düzeltilmedi:** bölünen şarkılarda bas Expert F1 0,03-0,04 düşüyor (First Date 0,892 → 0,859 `train`'de, 1981 0,859 → 0,816, Kids 0,796 → 0,768), gitar Expert 0,01-0,02. Bölünmüş haritanın 16'lık ızgarası 191 BPM'de 78 ms aralıklı; geç gelen onset'ler (ör. insan 41,715, onset 41,782) yanlış 16'lığa oturuyor (41,814), yarı tempoda 157 ms'lik ızgarada yerinde kalıyordu (`bas_dusus.py`: yerleşimden sonra recall 0,883 → 0,851). Düşüş First Date'te test ölçümünden önce de görünüyordu ama test ölçüldükten sonra fark edildi; kural gereği 1. adım değiştirilmedi. Öneri: 150 BPM ilkesini oturtma ızgarasına da uygulamak (16'lık 0,1 sn'den kısaysa sekizliğe oturt), bu yarı tempodaki yerleşimi aynen geri getirir. Proje sahibi bunu 2. adımın ilk maddesi yaptı.
- **Sabit test değerleri** (proje sahibi onayladı ve güncellendi; 3 test, LastResort; testlerde eski değerler ve "tempo kulakla doğrulandı, yeni hâli henüz çalınmadı" yorumu duruyor; tempo testine "vuruş ikiye bölündü" denetimi eklendi): gitar hash'i `f0c93106…a3d84f` → `d3a9782f…4c0e14`, bas hash'i `d7a7fee5…5643302f` → `d2c687a2…c881017`, `test_last_resort_real_grid_did_not_move` tempo olayları `(0, 81.812), (192, 85.622), (1728, 90.051), (5376, 90.597)` → `(0, 156.654), (192, 171.244), (3456, 180.102), (10752, 181.194)` (sonrakiler tam iki katı; girişe giden ilk parça yeniden hesaplanıyor). Danza, Toca ve Şarkı Testi'nin dört hash testi değişmeden geçti.
- **Testler:** yeni `tests/test_double_time.py` (16 test: snare kuralı, kick sızıntısı, tavan, az snare, sessiz davul, uçtan uca 190 BPM, 95 BPM'nin kalması, `--bpm`, davulsuz, davul alt sınırları, 150 BPM'de değişmezlik, `select_positions` alt sınırı, sustain alt sınırları); `test_drum_difficulty.py`'ye `min_gap_s` denetimi ve değerleri. Gerçek şarkı dışı bütün testler geçti (1018 test, 318 sn). `-Full` çalışmadı: LastResort bölünürse onun gitar ve bas hash'i ile `test_last_resort_real_grid_did_not_move` değişecek (proje sahibinin cevabından sonra güncellenir).

**2. adım: gitar Expert recall'ı (proje sahibi onayladı, 2026-11-15; SPEC 42).** Plan: (a) oturtma ızgarası, (b) uyarlamalı eşik, (c) vokal süzgecinin gerçek gitar notalarını silmesi. Kabul: `train` recall belirgin artar, precision en çok 0,03 düşer; Zombiler gerçek dışı örnek. Deneyler `outputs\_experiments\adim2_gitar\` (`onbellek.py` stem ve tempo önbelleği, `motor.py` Expert konumlarını `build_expert_track` adımlarıyla üretiyor ve evaluate'i birebir tutuyor, `tarama.py`, `secilen.py`, `zombiler_kulak.py`).
- **(a)** `charter._quantize`: bir 16'lık 150 BPM'deki süresinden (0,1 sn) kısaysa oturtma ızgarası sekizlik; sekizliklerden uzak bir onset kendi zamanında kalıyor. Gitar, bas ve keys'te ortak; bu bas Expert'i "ayarlamıyor", 1. adımın bölünen şarkılarda bozduğu yerleşimi geri getiriyor. `train`'de yalnızca First Date'e dokunuyor (notalarının %100'ü), diğer 7 şarkı aynı. İnsan chart'ının gerçek 16'lıkları (tek 16'lık konumlar): Holiday 1, Californication 171, Dani 269, Parallel Universe 638, Scar Tissue 177, Fat Lip 181, In Too Deep 159, First Date 0; (a) bunlara dokunmuyor, (a)+(b)+(c) ile bulunma oranları arttı (Dani 0,56 → 0,76, PU 0,64 → 0,84, ITD 0,21 → 0,50). First Date bas Expert 0,859 → 0,895 (1. adımdan önce 0,892).
- **Teşhis:** kaçırılan insan notalarının hepsinin 70 ms içinde zarf tepesi var; onları uyarlamalı eşik (MAD ve yerel oran) eliyor. Kayıtlı `guitar.opus` ile recall 10-25 puan yükseliyor (Demucs vuruş başlarını yumuşatıyor) ama In Too Deep'te değil (orada darboğaz tamamen eşik). Demucs gitar stem'inin enerjisinin en çok %0,3'ü kayıtlı gitarın sessiz olduğu yerlerde: sızıntı ihmal edilebilir. Vokal süzgeci `train`'de 587 nota siliyordu, 464'ü insan chart'ında var (PU'da 195'in 192'si). Silinen gerçek ve sahte notaları seviye ayırıyor (stem ortanca -10,2 / -15,5 dB, vokal üstünlüğü 7,1 / 11,3 dB); aynı anda vokal onset'i ya da spektral benzerlik ayırmıyor.
- **(b)+(c)** (`tarama.py`: 11 onset ayarı × 5 süzgeç ayarı, sonra 1,3-1,5 aralığında ince tarama): precision kaybı en çok 0,03 olan en iyi ortalama F1: gitara özel onset (`instruments.GUITAR_ONSETS`: MAD 2,5, yerel oran 1,5; bas ve keys 3,0 / 1,75'te kaldı), süzgeç 12 dB / -17 dB (keys de bu dosyayı kullanıyor). Yerel oran 1,25'e inince F1 ~0,78'e çıkıyor ama precision 0,05-0,06 düşüyor.
- **`train` sonucu** (`train_karsilastirma.md`, 1. adımdan sonraya göre): gitar Expert P 0,849 → 0,822, R 0,539 → 0,721, F1 0,643 → 0,762 (medyan 0,635 → 0,774); RHCP 0,692 → 0,769, RHCP dışı 0,594 → 0,755. Her şarkıda F1 arttı (First Date 0,534 → 0,686, Holiday 0,781 → 0,875, Californication 0,794 → 0,801, Dani 0,705 → 0,795, PU 0,665 → 0,812, Scar 0,604 → 0,666, Fat Lip 0,544 → 0,706, ITD 0,515 → 0,753). Alt seviyeler: Hard 0,586 → 0,703, Medium 0,509 → 0,643, Easy 0,493 → 0,627. Sustain payı 0,244 → 0,134 (insan 0,096). Bas Expert yalnızca First Date'te değişti (0,859 → 0,895). Gerileme: insan şerit değiştirince yön 0,315 → 0,269 (RHCP dışı 0,200 → 0,139): daha çok nota, aynı şerit eşlemesi; 3. adımın konusu. Californication'da hiçbir kalite metriği 0,02'den fazla düşmedi (R +0,026, Medium F1 +0,027, Easy F1 +0,024; el hareketi 0,658 → 0,634 ve alt seviye sustain payları birer pay, puan değil).
- **Test seti** (ayarlar dondurulduktan sonra bir kez; `test_karsilastirma.md`): gitar Expert F1 0,578/0,588 → 0,684/0,744 (Q ve 1981 hariç 0,702 → 0,778), P 0,851 → 0,826, R 0,460 → 0,604; Hard 0,483 → 0,586, Medium 0,408 → 0,495, Easy 0,381 → 0,484; bas Expert iki hızlı şarkıda 1. adımdan önceki değerine döndü (1981 0,816 → 0,859, Kids 0,768 → 0,797). Şarkı başına gitar F1: 1981 0,504 → 0,740, We Will Rock You 0,403 → 0,441, Otherside 0,733 → 0,749, Kids 0,671 → 0,808.
- **Zombiler (gerçek dışı):** gitar Expert 254 → 605 nota; süzgeç 482 yerine 216 nota siliyor (en çok 120-135 sn: 48, 105-120 sn: 31). Kulak testi dosyaları: `zombiler_eklenen_notalar.wav` (yeni ayarın tuttuğu, eskinin tutmadığı 351 nota) ve `zombiler_suzgecin_sildigi.wav` (hâlâ silinen 216 nota); sol kanal Demucs gitar stem'i, sağ kanal yalnızca click.
- **Değişen testler:** `test_tuning_bass_leaves_guitars_settings_alone[audio/vocal_bleed.toml]` (gitarın kendi ayarı değişti; eski hash yorumda). Yeni `tests/test_guitar_recall.py` (6 test: sekizlik ızgara ve kendi zamanında kalan onset, 150 BPM'de değişmezlik, yalnızca gitarın kendi onset ayarı, enstrümanların charter'a verdiği ayar, şarkıcının altındaki gitarın kalması, eski sınırların onu silmesi). Gerçek şarkı dışı bütün testler geçti (1024 test, 316 sn). Sabit değerler (proje sahibi onayladı, güncellendi; testlerde eski değerler ve "henüz çalınmadı" yorumu duruyor): LastResort gitar `d3a9782f…` → `f43b6e8d…d21b761`, LastResort bas `d2c687a2…` → `4d1f34ac…2f30cc42` (yalnızca (a)), Şarkı Testi gitar `fa099c6c…` → `a43fdd09…250b0c94` (proje sahibinin çaldığı gitar, bu sürüm çalınmadı). Danza, Toca ve Şarkı Testi'nin bas hash'leri değişmedi.
- **Zombiler kulak testi** yapılmadı (proje sahibi, 2026-11-15). Süzgecin Zombiler'de hâlâ sildiği 216 nota 3. adımın başında yalnızca `train` verisine dayanarak yeniden değerlendirilecek; Zombiler yalnızca gerçek dışı örnek olarak raporlanır.

2. adım `70919a4`'te kapandı (`-Full` 1045 test, 657 sn).

**3. adım: gitar şerit dağılımı, sustain, şerit değişince yön (2026-11-15; plan onaylandı; commit edildi, `29419df`; SPEC 43).** Deneyler `outputs\_experiments\adim3_gitar\` (`motor3.py` gitarı build'le bire bir üretiyor; `sonuc_3.py` artımlı tabloyu `train_karsilastirma_3.md`'ye yazıyor; `dogrula_3.py`: proje kodu seçilen varyantla 9 şarkıda aynı).
- **Vokal süzgeci, yalnızca `train`'le** (`zombiler_suzgec.py`): `train`'de süzgeç açık/kapalı gitar Expert F1 ortalaması 0,7616 / 0,7612, medyanı 0,7737 / 0,7774: etkisi yok denecek kadar az. Şarkı başına notaların %0,2-2,9'unu siliyor, toplam 78 nota, 31'i insan chart'ında var (%40). Zombiler (gerçek dışı): 821 notanın 216'sı (%26,3), `train`'in en yükseğinin ~9 katı, yani `train`'in kapsamı dışında. Silinen notaları `train`'de gerçek olanlardan çok sahte olanlara benziyor (vokal üstünlüğü ortanca 22,5 dB; `train` sahte 22,4, gerçek 15,8). `train`'in hücre hücre gerçek oranlarıyla 216'nın ~67'si gerçek sayılırdı (26'sı 5'ten az `train` notalı hücrelerden, genel %40 oranıyla). Öneri: değişiklik yok.
- **Teşhis** (`teshis.py`, `yon_teshis.py`; build'in yaptığı gibi, `train` 8 şarkı):
  - Yön: insan şerit değiştirince biz %61 yerinde kalıyoruz (RHCP dışı %79), %12 ters, %27 aynı yön. Şerit eşleyici sorun değil: konturumuz doğru yöne gidince %82 izliyor. Sorun kontur: insanın hareketlerinin %51'inde (RHCP dışı %74) tekrar kuralı (spektral benzerlik ≥ 0,95 önceki değeri kopyalıyor) konturu düzlüyor. Distortion'lı şarkılarda benzerlik akor değişimini tekrardan ayırmıyor (ortanca hareket 0,966 / tekrar 0,979; RHCP 0,917 / 0,967). Zorla düzlenen adımlarda ham konturun işareti insanla %64 uyuşuyor (zayıf ama bilgi var). İnsan yerinde kalınca biz %16 hareket ediyoruz. Şarkı başına: First Date 0,03, Holiday 0,08, PU 0,14, Fat Lip 0,21, ITD 0,24, Dani 0,40, Scar 0,43, Californication 0,62.
  - Şerit (yeşil/kırmızı/sarı/mavi/turuncu): Expert bizim 0,148/0,285/0,316/0,243/0,008, insan 0,205/0,236/0,237/0,225/0,097. İnsanın turuncusunda biz %45 mavi, %29 sarı koyuyoruz. Nedenler: `register_span` [0,5, 3,0] (öbeğin en tiz notası bile maviye yöneliyor), turuncu önseli 0,06. Alt seviyeler aşağı sıkışık: Hard bizim 0,310/0,323/0,246/0,117/0,004, insan 0,208/0,230/0,246/0,207/0,110; Medium mavi 0,027, insan 0,196 (`chord_lane_map` [0,0,0,1,2], Medium `lane_map` [0,1,1,2,3]).
  - Sustain: Expert payı 0,134, insan 0,096 (RHCP dışı 0,194 / 0,107); P 0,36, R 0,54, F1 0,36. Çınlama süremiz pratikte sonraki notaya kalan süreye eşit (ortanca oran 1,00, insan sustain'lesin ya da sustain'lemesin): 12 dB'lik bırakma eşiği distortion'lı gitarda tetiklenmiyor, karar fiilen "arada boşluk var mı". Alt seviyeler Expert'ten alıyor: Medium/Easy RHCP dışı 0,116/0,164, insan 0,010/0,018 (RHCP insan 0,094/0,119: üsluba bağlı).
- **Proje sahibinin kararları (2026-11-15):** süzgeç sınırları aynı, notaların %5'inden fazlasını silerse terminalde ve `analysis.json`'da uyarı; 3c 3. adımda; alt seviye sustain'i tek ayar, `train` ortalamasına göre, üslup algılama yok; onay 3a-3d bitince tek seferde, artımlı tabloyla. Ek kriterler: insan kalınca kalma en çok 0,03 düşer; Expert el hareketi insanınkinin 1,2 katını aşmaz; gerçek tekrarlı riff'ler zıplamaz; gitarda "turuncu = tek perde" kontrolü (%70 üstü uyarı), `train` dağılımı raporlanır.
- **3a, tekrar kuralı** (`pitch.PitchConfig.raw_repeat_percentile`, `NotePitch.raw_similarity`, `instruments.GUITAR_PITCH`; yalnızca gitar). Denenip bırakılanlar (`ozellik_3a*.py`, `tarama_3a*.py`): şarkıya göre log benzerlik eşiği (P30: yön 0,323 ama kalma 0,788), spektrumun alçak kısmı, kroma, kök, önceki/sonraki notaların ortalaması (hiçbiri bugünkünden iyi ayırmıyor, AUC 0,70-0,77), ölçüdeki yer (şarkıya göre ters işaret), eşleyicinin `consistency` ve `repeat` ağırlıkları. Seçilen: log benzerlik ≥ 0,95 **ve** ham (log'suz) benzerlik ≥ şarkının 14. yüzdeliği; yön tabanını (0,315) geçen en hafif ayar.
- **3b, Expert şeritleri** (`fret_weights.toml`: `register_span` [0, 3,5], `register` 1,0, `lane_prior` 1,0, `lane_shares` `train` insan ortalaması; keys de bu dosyayı kullanıyor). Akor şekli önseli denendi, bırakıldı: turuncuyu yok ediyor, en sık akor payını 0,37'den 0,55'in üstüne çıkarıyor. Bütün şarkılara ortak tek bir dağılımın tabanı (insanların `train` ortalamasından şarkı başına uzaklığı) Expert'te 0,073; ulaşılan 0,139. Bizde (0,3) ve (1,4) şekilleri yok (kesin kural listesi `SHAPES`), insanda %7: değiştirilmedi.
- **3c, alt seviye şeritleri** (`difficulty.toml`): Medium `lane_map` [0,1,2,3,3], Easy [0,0,1,2,2]; Hard'a dokunulmadı (en iyi ayar 0,157'yi 0,154'e indiriyor ama Californication Hard'ı 0,078'den 0,250'ye çıkarıyor). Yumuşak hedefler `train`'den: şerit payları ortalama, sustain aralıkları insanların hepsini kapsıyor (Hard [0, 0,33], Medium [0, 0,16], Easy [0, 0,21]); gitar için `[orange_pitches]` 0,70.
- **3d, sustain** (`sustain.cut_at_reattacks`, `charter.build_expert_track(reattack_config=...)`, `instruments.GUITAR_REATTACKS` MAD 1,0 / yerel oran 1,1, en az 0,10 sn sonra; yalnızca gitar). Bırakma eşiği (12'den 4 dB'e) ve en kısa sustain (0,75'ten 2 vuruşa, 0,30'dan 0,45 sn'ye) F1'i hep düşürdü; Medium/Easy `min_sustain_beats` 0,75 payı 0,17/0,22'ye fırlattı, 1,0'da kaldı.
- **`train` sonucu** (ortalama; artımlı bugün → +3a → +3b → +3c → +3d): nota F1 0,762 hepsinde aynı; yön (insan hareket edince) 0,269 → 0,318 → 0,316 → 0,316 → 0,316 (RHCP dışı 0,139 → 0,212); tüm adımlar 0,645 → 0,652; insan kalınca kalma 0,844 → 0,830 → 0,832 (−0,012; sınır 0,03); tekrarlı riff (≥4 nota, hiç zıplamadan) 0,589 → 0,546 → 0,528 (First Date 0,95 → 0,79, Holiday 0,95 → 0,82, PU 0,64 → 0,53; önce hiç kıpırdamıyorlardı); el hareketi 0,396 → 0,446 (insan 0,531, sınır 0,637); akor uyumu 0,671 → 0,670; en sık akor payı 0,382 → 0,366; turuncu 0,008 → 0,097 (insan 0,097); sarı 0,316 → 0,297 (0,237); yeşil 0,148 → 0,126 (0,206); en kötü şerit farkı Expert 0,161 → 0,139, Hard 0,202 → 0,157, Medium 0,186 → 0,119, Easy 0,158 → 0,105; sustain payı 0,133 → 0,092 (insan 0,087), sustain F1 0,358 → 0,382; Hard/Medium/Easy sustain payı 0,176/0,082/0,112 → 0,124/0,043/0,062 (insan 0,126/0,058/0,075); şerit merkezi korelasyonu 0,219 → 0,191.
- **Kabul kriterleri.** Tuttu: konumlar aynı, yön ≥ 0,315 (0,316), tüm adımlar düşmedi, kalma −0,012, el hareketi ≤ 1,2 × insan, akor uyumu −0,001, en sık akor payı artmadı, turuncu ≥ 0,05, Medium ≤ 0,12, Easy kötüleşmedi, sustain payı farkı ≤ 0,03, bas bayt bayt aynı. Tutmadı: yön hedefi 0,35; Expert en kötü şerit farkı ≤ 0,10 (0,139); Hard ≤ 0,12 (0,157); sustain F1 ≥ 0,45 (0,382); RHCP dışı Easy sustain ≤ 0,06 (0,067) ve RHCP Medium/Easy ≥ insanın yarısı (0,039/0,057; sınır 0,047/0,060): tek ayar kararının sonucu. Riff'lerde zıplama arttı (yukarıda).
- **Californication** (0,02'den fazla kötüleşen; proje sahibi kabul etti, 2026-11-15): şerit merkezi korelasyonu 0,423 → 0,378; Expert en kötü şerit farkı 0,155 → 0,193 (turuncu 0,020 → 0,174, insanınki 0,048); Hard 0,054 → 0,078. İyileşenler: sustain F1 0,692 → 0,695, Easy şerit farkı 0,081 → 0,060, riff 0,154 → 0,231. Yön 0,618 → 0,604.
- **Turuncu kontrolü, `train` dağılımı** (en sık spektral merkezin turuncudaki payı / turuncu nota sayısı): Expert First Date 0,42/91, Holiday 0,76/45 (uyarır), Californication 0,41/215, Dani 0,25/79, PU 0,38/164, Scar 0,22/64, Fat Lip 0,38/89, ITD 0,64/97; Hard'da yalnızca First Date uyarır (0,93/15). İnsanın turuncusu bizim konturumuzla okununca ortalama 0,33, en çok 0,58 (ITD).
- **Test seti** (ayarlar dondurulduktan sonra bir kez; `test_karsilastirma.md`; ölçümden sonra hiçbir şey değişmedi): gitar Expert F1 0,684 aynı; yön 0,234 → 0,274 (Queen ve 1981 hariç 0,278 → 0,301); tüm adımlar 0,689 → 0,679; turuncu 0,004 → 0,126 (insan 0,154); sarı 0,436 → 0,288 (0,185); en kötü şerit farkı Expert 0,276 → 0,233, Hard 0,187 → 0,183, Medium 0,254 → 0,182, Easy 0,438 → 0,281; el hareketi 0,373 → 0,427 (0,629); sustain payı 0,157 → 0,120 (insan 0,216: test insanları daha çok sustain'liyor), sustain F1 0,399 → 0,406; alt seviye F1'leri +0,002/+0,003; bas aynı.
- **Tekrarlı riff ölçüsünün insan karşılığı** (`riff_insan.py`; proje sahibinin isteği). "≥4 notalık tekrarlı riff zıplamadan" insanın kendi aynı-şerit dizileri üzerinde ölçülüyor, insan tanım gereği 1,0 alır. İki tarafa aynı uygulanan ölçüler (eşleşen konumlarda, en alçak şerit; önce → sonra, insan): ≥4 notalık aynı-şerit dizilerindeki nota payı 0,723 → 0,685 (0,579); ortalama dizi uzunluğu 8,28 → 4,75 (3,12); şerit değiştirme sıklığı 0,251 → 0,282 (0,373). RHCP dışı: 0,852 → 0,800 (0,527), 11,8 → 5,7 (2,7), 0,144 → 0,202 (0,399); RHCP: 0,593 → 0,570 (0,630), 4,77 → 3,76 (3,52), 0,357 → 0,362 (0,347). Yani düşüş insana yaklaşma: chart'larımız hâlâ insanınkinden durağan (RHCP hariç). Ama yeni hareketlerin bir kısmı insanın tuttuğu dizilerin içine düşüyor (insanın dizilerinde zıplamadan kalma 0,589 → 0,528); ikisi birlikte doğru.
- **Gerçek dışı örnekler** (`gercek_disi.md`, gitar, `70919a4` → şimdi): LastResort sustain Expert 0,201 → 0,107, Easy 0,290 → 0,104; turuncu 0,002 → 0,081 (en sık merkez %33); Medium mavi 0,007 → 0,159. Zombiler: süzgeç yine 821 notanın 216'sını siliyor ve artık uyarıyor; sustain Easy 0,107 → 0,059; turuncu 0,009 → 0,043.
- **Değişen testler:** `test_tuning_bass_leaves_guitars_settings_alone` (fret_weights, difficulty, vocal_bleed hash'leri: gitarın kendi dosyaları), `test_each_instrument_reads_its_own_files` (gitarın turuncu sınırı None → 0,70), `test_chord_rule` (Medium (3,) → (3,), Easy (1,2,4) → (0,)), `test_bad_configuration_is_refused` (yalnızca aranan satırlar yeni değerlere), iki gitar hash'i (LastResort `f43b6e8d…` → `737bc3b8…597ac6f`, Şarkı Testi `a43fdd09…` → `0350be9a…a9e429c5`; proje sahibi onayladı). Yeni `tests/test_guitar_lanes_sustain.py` (26 test). Hızlı kademe 918 test 50 sn, `-Mid` 1050 test 341 sn; gerçek şarkı testlerinin 21'i, iki gitar hash'i dışında geçti, güncellenen hash'lerle o ikisi de geçti.

**4. adım: davul (2026-11-15/16; plan onaylandı; proje sahibi B'yi seçti; `-Full` 1093 test, 688 sn; commit edildi; SPEC 44).** Deneyler `outputs\_experiments\adim4_davul\` (`onbellek.py`: `train`'in davul chart'ı olan 7 şarkısının davul stem'i, tempo haritası ve insan davulu; Parallel Universe disco flip yüzünden okunmuyor, Fat Lip'te yalnızca Expert; `teshis.py`, `teshis.log`). Davul 1. adımdan beri değişmedi.
- **Bugün (`train` ortalaması, 2. adımın raporu):** Expert konum F1 0,892, kick 0,969, snare 0,808, zil 0,742 (RHCP dışı 0,682), tom ~0; hi-hat/ride aynı şerit 0,680; en kötü gem farkı 0,148. Seviyeler: kick F1 Hard 0,836, Medium 0,780, Easy 0,399 (RHCP dışı 0,267); zil F1 Easy 0,607.
- **Gem payları (bizim / insan):** Expert mavi zil 0,26 / 0,12, yeşil zil (crash) 0,01 / 0,10, sarı zil 0,16 / 0,19, tom 0,01 / 0,03. Easy mavi 0,40 / 0,23, yeşil 0,01 / 0,18 (RHCP dışı 0,23), kick 0,21 / 0,10 (RHCP dışı 0,28 / 0,10).
- **Zil karışıklığı (Expert, eşleşen konumlar):** insan hi-hat'i (1871) bizde %56 sarı, %34 mavi; insan ride'ı (1227) %78 mavi; insan crash'i (852) %59 mavi, %37 zilsiz, %2 yeşil. Neden: `drum_hits.toml` `[cymbal_kinds]` çınlaması uzun her zili ride sayıyor; crash için kick, en güçlü ziller kadar güç ve 0,6 sn sonra çınlama birlikte gerekiyor (Californication'dan, "doğrulanmadı"). İnsan crash'lerinin yalnızca yarısı kick'le (First Date 0,53, Dani 0,47, Fat Lip 0,50), ölçü başında olanlar az (Dani 0,17, Fat Lip 0,11): Dani ve Fat Lip'te crash nakaratlarda ride gibi çalınıyor.
- **Tom'lar:** insan Expert'te çoğu Holiday (173) ve First Date'te (76); orada biz kick+sarı zil, sarı zil ya da snare+zil yazıyoruz. Tom dedektörü gerçek veride hiç çalışmıyor.
- **Alt seviyelerde kick (konum bileşimi, bizim / insan):** Medium'da tek başına kick 0,12 / 0,00 (RHCP dışı 0,19 / 0,01); Easy'de tek başına kick 0,25 / 0,12 (RHCP dışı 0,34 / 0,12); Hard 0,15 / 0,08. İnsan Medium'da kick'i hep bir pad'le yazıyor, Easy'de hiç pad'le yazmıyor (bizde de kural).
- **Plan (sunuldu):** 4a Expert zil türleri (hi-hat / ride / crash; önce eşleşen insan zillerinde ses özellikleri ölçülür, sonra `[cymbal_kinds]` ve gerekirse yeni özellik); 4b alt seviye gem seçimi (tek başına kick, zil seçimi Expert'ten); 4c davul yumuşak hedefleri `train`'den. Tom'lar ayrı karar (öneri: şimdilik değil). Kabul kriterleri ve kararlar proje sahibine sunuldu.
- **Proje sahibinin kararları (2026-11-15):** tom'lar açık konu, 4. adımda yok; crash'li nakaratlar için sesle ayırma denenir, yazdığımız crash'lerin en az yarısı insanınkine denk gelmezse mavi kalır, yalnızca vurgu crash'leri eklenir; Medium'da tek başına kick kesin kural değil, tercih; onay 4a-4c bitince tek seferde, artımlı tabloyla. Ek: Zombiler'in Easy kick-snare kalıbı 4b'den sonra raporlanacak (ilk 30 sn: nota/sn, kick payı, en uzun kesintisiz kick-snare dizisi).
- **Motor:** `motor4.py` davulu `build_tracks_for` ile bire bir üretiyor (8 şarkı; her zil vuruşunun özellikleri kayıtlı, zil kuralı yeniden hesaplanınca da aynı); `dogrula_4.py`: proje kodu seçilen varyantla 8 şarkıda aynı.
- **4a, zil türleri** (`drum_hits.py` `_cymbal_kind`, `drum_hits.toml` `[cymbal_kinds]`): `ozellik_4a.py` (her zil vuruşu eşleşen insan ziliyle etiketli), `tarama_4a*.py`. Ayıranlar: hi-hat/ride için 0,09 sn'deki çınlama (AUC 0,735), kick'le gelme ve güç; crash/ride için çınlama (0,84), snare'siz gelme, orta frekans, sonraki zile boşluk (0,74). Seçilen (H): çınlama < 0,4 ya da kick'le, güç ≥ 0,9 ve çınlama < 0,6 → hi-hat; değilse çınlama ≥ 0,65 ve sonraki zil ≥ 0,35 sn → crash; kalanı ride. Crash eşiği 0,6 daha çok yeşil veriyordu ama `train` isabeti %52'de kalıyordu; "kick'le güçlü hi-hat" ekinin sert hâli (0,8 / 0,65) Californication'ın Easy gem farkını +0,024 bozuyordu. 0,25 sn'de ikinci çınlama koşulu `train`'i kötüleştirdi, alınmadı.
- **4b, tek başına kick** (`drum_difficulty.py` `_keep_lone_kicks`, `lone_kick_share` Hard 0,75 / Medium 0,5 / Easy 0,75): puan cezası işe yaramadı (aralık kuralı yuvaları azaltıyor, yuvasında tek kalan kick her puanla seçiliyor); pay biçiminde, konum F1'ini 0,02'den fazla düşürmeyen en düşük paylar. Easy'ye özel "hi-hat kick'ten önce" gem sırası Easy kick F1'ini 0,015'e indiriyordu (Californication 0,588 → 0); "kick + hi-hat'te kick payı" Zombiler'in şarkı boyu dizisini 61 → 25-31'e kırıyor ama Easy kick F1 0,468 → 0,39-0,41, Californication Easy kick F1 0,588 → 0,466: alınmadı (insanlar kick + hi-hat'te Easy'de kick'i %62 tutuyor, ölçüdeki yerden bağımsız; hızlı First Date'te %59'unu atıyor).
- **4c:** `drum_difficulty.toml` alt seviye `gem_shares` = `train` insan ortalaması (yalnızca yumuşak hedef, chart değişmiyor).
- **`train` sonucu** (ortalama, bugün → +4a → +4b; `train_karsilastirma_4.md`): Expert konum/kick/snare/zil F1 aynı (0,889/0,969/0,807/0,741); hi-hat/ride aynı şerit 0,681 → 0,700; zil türü doğru 0,480 → 0,540; crash isabeti (şarkı ortalaması) 0,311 → 0,543 (toplam 282/509); Expert en kötü gem farkı 0,149 → 0,111; mavi 0,261 → 0,214 (insan 0,122); yeşil 0,007 → 0,046 (0,096); seviye konum F1 Hard 0,863 → 0,868, Medium 0,907 → 0,907, Easy 0,874 → 0,862; kick F1 Hard 0,835 → 0,847, Medium 0,780 → 0,787, Easy 0,399 → 0,468; gem farkı Hard 0,143 → 0,090, Medium 0,173 → 0,123, Easy 0,238 → 0,157; tek başına kick Hard 0,163 → 0,132 (insan 0,080), Medium 0,122 → 0,077 (0,005), Easy 0,255 → 0,218 (0,122); Easy kick payı 0,208 → 0,176 (0,100). Expert zil karışıklığı (insan → bizim): hi-hat Y 0,56 → 0,58, B 0,34 → 0,30; ride B 0,78 → 0,71; crash G 0,02 → 0,31, B 0,59 → 0,30, zilsiz 0,37 → 0,37.
- **Kabul kriterleri.** Tuttu: Expert konum/kick/snare F1 değişmedi, Californication alt sınırları, seviye konum F1 en çok −0,012, Easy kick F1 belirgin arttı, crash isabeti `train`'de ≥ 0,5. Tutmadı: hi-hat/ride ≥ 0,75 (0,700), zil türü ≥ 0,60 (0,540), mavi ≤ 0,18 (0,214), yeşil ≥ 0,05 (0,046), Expert gem farkı ≤ 0,10 (0,111), tek başına kick Hard ≤ 0,10 / Medium ≤ 0,03 / Easy ≤ 0,15 (0,132 / 0,077 / 0,218). Californication: 0,02'den fazla kötüleşen yok; Easy tek başına kick 0,103 → 0,127 (insan 0,099) insandan 0,024 uzaklaştı, Easy kick F1 0,549 → 0,588.
- **Test seti** (dondurulduktan sonra bir kez; `test_karsilastirma.md`, `test_crash.py`): Expert konum/kick/snare/zil F1 aynı; hi-hat/ride aynı şerit 0,326 → 0,359; Expert gem farkı 0,284 → 0,260; mavi 0,321 → 0,276 (insan 0,037); yeşil 0,025 → 0,059 (insan 0,024); seviye konum F1 Hard 0,863 → 0,867, Medium 0,929 → 0,927, Easy 0,818 → 0,811; Easy kick F1 0,270 → 0,309. **Crash isabeti testte 43/288 = %15** (1981 %21, We Will Rock You 0/100, Otherside %17, Kids %50; Queen hariç %23): `train`'deki %55 genellenmedi. İnsan hi-hat'i testte bizde %57 mavi.
- **Seçenekler (yalnızca `train`; test yeniden ölçülmedi, `secenek_4a.py`):** A şimdiki (zil türü 0,540, gem farkı 0,111, yeşil 0,046); B hi-hat iyileştirmesi kalır, crash eski kurala döner (0,490, 0,146, yeşil 0,003, isabet 19/35); C 4a geri alınır (0,480, 0,149). 4b ve 4c üçünde aynı.
- **Proje sahibinin kararları (2026-11-16):** (1) B: hi-hat iyileştirmesi kalır, crash eski sıkı kurala döner, vurgu crash'i eklenmez; B önceden konan "isabet tutmazsa mavi bırak" kuralının uygulaması. (2) B için test seti bir kez daha, yalnızca raporlamak için ölçüldü; sonuç ne olursa olsun bu adımda değişiklik yok. **Test seti 4. adımda iki kez görüldü** (A ve B). (3) Zombiler'in Easy kalıbı 5. adımda: `train`'de tek hızlı şarkı (First Date) olduğu için ince ayar değil, ilke tabanlı kural (ör. 150 BPM üstünde Easy'de kick + hi-hat konumlarına saniye cinsinden yoğunluk sınırı), test setindeki 1981 ve Kids ile sınanacak. (4) Tutmayan hedefler ve tom'lar açık konu.
- **B, `train`** (bugün → +4a → +4b; `train_karsilastirma_4.md`, A ayrı sütunda): Expert konum/kick/snare/zil F1 aynı; hi-hat/ride aynı şerit 0,681 → 0,691; zil türü doğru 0,480 → 0,490; insan hi-hat'leri sarı 0,56 → 0,58; crash isabeti (şarkı ortalaması) 0,311 → 0,564, ama yeşil 0,007 → 0,003; Expert gem farkı 0,149 → 0,146; mavi 0,261 → 0,257; 4b'nin etkisi A'dakiyle aynı (seviye konum F1 Hard 0,868 / Medium 0,907 / Easy 0,862; Easy kick F1 0,399 → 0,468; tek başına kick 0,132 / 0,077 / 0,218); gem farkı Hard 0,143 → 0,138, Medium 0,173 → 0,165, Easy 0,238 → 0,233. Californication: 0,02'den fazla kötüleşen yok; Easy tek başına kick 0,103 → 0,127 (insan 0,099) insandan 0,024 uzaklaştı (4b'den), Easy kick F1 0,549 → 0,588.
- **B, test seti (ikinci bakış, yalnızca rapor; `test_karsilastirma_B.md`, `test_crash_B.log`):** Expert konum/kick/snare/zil F1 aynı; hi-hat/ride 0,326 → 0,340; gem farkı 0,284 → 0,281; mavi 0,321 → 0,318 (insan 0,037); yeşil 0,025 → 0,017 (insan 0,024); seviyeler A ile aynı. Eski crash kuralının testte isabeti de düşük: 9/79 = %11 (We Will Rock You 37/37 yanlış), ama A'nın 288 crash'ine karşı 79. İnsan hi-hat'i testte bizde %63 mavi.
- **B, gerçek dışı örnekler** (`gercek_disi.md`): LastResort yeşil 0,007 → 0,005 (A'da 0,105'e çıkıyordu), sarı 0,171 → 0,182, Easy ilk 30 sn 1,83 → 2,03 nota/sn, kick 0,13 → 0,18; Zombiler değişmedi (Easy ilk 30 sn 2,1 nota/sn, kick payı 0,325 → 0,342, en uzun kesintisiz kick-snare dizisi 25 konum, 18,4-26,2 sn).
- **B'nin değişen testleri:** `tests/test_drum_cymbals_kicks.py` B'ye göre (crash eski kural; "kick'le güçlü hi-hat eskiden ride'dı" testi); A için yapılan sentetik ride değişikliği geri alındı (`test_drum_hits.py` commit'teki gibi). Aşağıdaki A maddeleri karşılaştırma için duruyor.
- **Gerçek dışı örnekler** (`gercek_disi.md`, yalnızca davul, `29419df` → şimdi): LastResort crash Expert 0,007 → 0,105, Easy 0,013 → 0,195; mavi Expert 0,262 → 0,153; Easy ilk 30 sn 1,83 → 2,03 nota/sn, kick 0,13 → 0,18, en uzun kick-snare dizisi 7 → 6. Zombiler neredeyse değişmedi: Easy ilk 30 sn (ilk nota 1,68 sn) 2,1 nota/sn, kick payı 0,325 → 0,342, en uzun kesintisiz kick-snare dizisi 25 konum (18,4-26,2 sn) → aynı; şarkı boyu en uzun 61 (51,1-70,8 sn). Neden: 183 BPM'de düz rock ritmi, Expert'te 1 ve 3'te kick + hi-hat, 2 ve 4'te snare + ride; Easy'de kick ve snare kalıyor (insanlar da kick + hi-hat'te kick'i çoğunlukla tutuyor). Easy'de tek başına kick payı 0,42.
- **Değişen testler:** `test_a_known_kit_is_heard_part_by_part` (sentetik ride'ın sönümü 0,3 → 0,15 sn: `train`'in ride'ları 0,09 sn'de ortanca 0,55 tutuyor, 0,3 sn'lik sentetik ride 0,74 tutup crash'lerle (0,76) aynıydı; toleranslar aynı), `test_the_settings_cannot_decide_a_hard_rule_or_be_wrong` (Hard kick payının aranan satırı 0,159 → 0,231; yeni durum: `lone_kick_share` 1,5 reddedilir). Yeni `tests/test_drum_cymbals_kicks.py` (21 test). `-Mid` (hızlı kademe dahil) 1072 test 629 sn (makine yüklü), gerçek şarkı testleri 21/21 583 sn: gitar ve bas hash'leri değişmedi, onay bekleyen hash yok.

**5. adım planı (2026-11-16, proje sahibi onayladı; `-Full` 1102 test, 1347 sn; commit edildi): alt seviye oranları ve hızlı şarkıda Easy davul.**
- **Bugün** (`train` ortalaması, 2. adımın raporu; adımın başında güncel kodla yeniden ölçülecek), Expert'e oran bizim / insan, `.toml` hedefi, nota F1: gitar Hard 0,662 / 0,735 (RHCP 0,678, RHCP dışı 0,812), hedef 0,67, F1 0,703; bas Hard 0,652 / 0,761, hedef 0,72, F1 0,796; bas Medium 0,381 / 0,526, hedef 0,47, F1 0,744. Basta iki seviye kendi hedefine ulaşmıyor: büyük olasılıkla en kısa aralık (Hard 0,25 sn / 0,5 vuruş, Medium 0,40 sn) bağlıyor. Gitar Medium (0,427 / 0,462), gitar Easy (0,271 / 0,282) ve bas Easy (0,251 / 0,281) insana yakın, dokunulmuyor. Oran bizim Expert'imize göre; gitar Expert recall'ı 0,72 olduğu için aynı oran insandan seyrek demek, bu yüzden insan Hard'ına göre yoğunluk da raporlanacak.
- **5a gitar Hard:** önce hangi kuralın bağladığı (oran mı aralık mı); sonra `difficulty.toml` `[hard]` `position_ratio` (gerekirse `min_gap_s`) taraması. Seçim `train` Hard nota F1'iyle. Keys aynı dosyayı kullanıyor, keys Hard'ı da değişir (gerçek veriyle ölçülmüyor).
- **5b bas Hard ve Medium:** `train` insanlarının bas Hard ve Medium'daki en kısa aralıkları (saniye ve vuruş); aralık davuldaki gibi vuruş + 150 BPM'deki saniye tabanı (SPEC 41) biçimine geçebilir; sonra oran. Bas Expert'e dokunulmaz. Danza ve Toca'nın bas Hard ve Medium'unu proje sahibi tekrar çalar; beğenmezse 5b geri alınır.
- **5c Easy davul, 150 BPM üstü (Zombiler):** ilke tabanlı, `train`'de ince ayar yok. Önerilen kural: 150 BPM üstünde Easy'de kick + hi-hat konumundan gelen kick, önceki kick'ten en az 150 BPM'de iki vuruşun süresi (0,8 sn) uzaktaysa kalır, değilse konum düşer (hi-hat'e dönmez); korunan snare'ler ve öteki konumlar aynı. İnsanlar hızlı First Date'in Easy'sinde kick + hi-hat konumlarının %59'unu atıyor. Zombiler'in tipik ölçüsünde Easy K S K S → K S . S olur. Seçenek: Easy'nin bütün konumlarına saniyede 2,5 tavanı (150 BPM'de dörtlük). 150 BPM ve altındaki şarkılar bayt bayt aynı kalır.
- **Önerilen kabul kriterleri:** gitar, bas ve davul Expert'i aynı; `train` gitar Hard F1 düşmez, bas Hard ve Medium F1'i en çok −0,01, yoğunlukları insana yaklaşır; 5c'de 150 BPM ve altı bayt bayt aynı, First Date Easy konum F1'i en çok −0,02, Zombiler'de en uzun kesintisiz kick-snare dizisi 25'ten belirgin kısa; mevcut alt sınırlar kesin; Californication'da başka metrik 0,02'den fazla düşerse önce sorulur. Test seti adımın sonunda, dondurulduktan sonra bir kez (1981 ve Kids'in Easy davulu ayrıca raporlanır).
- **Değişecek sabit testler (onayla):** gitar hash'i dört seviyeyi kapsıyor (5a değiştirir); bas hash'leri dört seviyeyi kapsıyor (Danza, Toca, LastResort, cloneH; 5b değiştirir); `difficulty.toml` ve `bass_difficulty.toml` dosya hash'leri.
- **Proje sahibinin kararları (2026-11-16):** (1) 5c için R1: kick + hi-hat konumundan gelen kick, önceki kick'ten en az 0,8 sn uzaktaysa kalır, değilse konum düşer; 150 BPM ve altı bayt bayt aynı. (2) Onay 5a-5c bitince tek seferde, artımlı tabloyla; Danza ve Toca'yı ondan sonra çalar. (3) Kabul kriterleri uygun, eklerle: 5a'da gitar Hard F1'i yalnızca düşmemeli değil, belirgin yükselmeli (hedef olarak raporlanır), insan Hard'ına göre yoğunluk da verilir; oynanabilirlik: Hard ve Medium'daki en kısa aralıklar (gitar ve bas) `train` insanlarının aynı seviyedeki en kısa aralıklarının altına inmez; 5a'nın keys Hard'ını da etkilediği not edilir (aşağıda "Bilinen sınırlar"). Bitince: `train` sonuçları, test setinin tek ölçümü (1981 ve Kids'in Easy davulu dahil), Zombiler'in Easy kalıbı, onay bekleyen hash'ler ve `-Full` komutu.
- **Motor:** `outputs\_experiments\adim5_seviye\motor5.py` `train`'in 8 şarkısında gitar ve bas Expert'ini bir kez güncel kodla üretip saklıyor, alt seviyeleri istenen ayarla `reduce_track`'le yeniden kuruyor ve `evaluate`'in `compare_levels`'iyle ölçüyor (`verify`: bugünkü ayarla 16/16 aynı). 5c için 4. adımın motoru (`rule_b`) kullanıldı; proje kodunun `build_tracks_for`'uyla 8/8 aynı.
- **Teşhis** (`teshis_5.md`, `teshis_5a.md`): gitar Hard her şarkıda hedefine ulaşıyor (Parallel Universe dışında), yani oran belirliyor; yoğunluğu insan Hard'ının 0,84'ü (RHCP dışı 0,68). Bas Hard ve Medium hedefe ulaşamıyor, aralık kuralı bağlıyor (Medium'da First Date 131, Dani 116, Parallel Universe 397 konum eksik). İnsan Hard'ı bizim gitar Expert konumlarımızdan vuruşların %82-90'ını, sekizliklerin %70'ini (zayıf çeyrekte %55, güçlüde %84), on altılıkların %23'ünü (güçten bağımsız) tutuyor. Bizim Expert'ten kurulabilecek en iyi Hard'ın F1'i ortalama 0,862 (bugün 0,703).
- **5a gitar Hard** (`tarama_5.py guitar hard`, `tarama_5a2.py`): `position_ratio` 0,67-0,90 taraması; en iyi 0,80 (F1 0,703 → 0,718; RHCP dışı 0,701 → 0,727). `min_gap_s` 0,13 fark etmedi. Puan tabanı (zayıf konumlar hedef dolmasa da girmez) en çok 0,724 verdi, yeni mekanizmaya değmediği için alınmadı. Medium ve Easy değişmedi (bir üst seviyeden seçiyorlar, en iyi puanlılar aynı). Şarkı başına: In Too Deep +0,076, Californication +0,025, First Date +0,020, Dani +0,017, Parallel Universe aynı, Holiday −0,017, Scar Tissue −0,018.
- **5b bas** (`tarama_5.py bass hard|medium`): Hard'da en iyi ayar (0,80, 0,15-0,20 sn) F1'i +0,01 artırıyordu ama Californication bas Hard'ını onaylı alt sınırın (0,77) altına indiriyordu (0,767); sınır içinde en iyisi +0,004 (0,72 / 0,20 sn) ve 0,20 sn dört `train` şarkısında aralığı o şarkının insanının en kısasının altına indiriyordu: **bas Hard değişmedi.** Medium: `min_gap_beats = 1.0` (dörtlük her zaman kalabilir; Hard'daki sekizlik kuralının bir seviye aşağısı; 150 BPM ve altında etkisiz), `position_ratio` 0,47 → 0,50. 0,30 sn tabanı yoğunluğu insana daha çok yaklaştırıyordu ama Californication bas Medium'unu 0,02'den fazla düşürüyordu, alınmadı.
- **5c** (`olc_5c.md`, `test_fast_easy_drums.py`): R1, `drum_difficulty.toml` `[easy]` `fast_kick_hihat_gap_beats = 2.0` (150 BPM'de 2 vuruş = 0,8 sn; yerel tempo `FLOOR_BPM`'in üstündeyse). `train`'de yalnızca First Date değişiyor (öteki 6 davullu şarkının en yüksek yerel temposu ≤ 146,5 BPM, bayt bayt aynı). First Date Easy: konum F1 0,869 → 0,865, kick F1 0,392 → 0,252 (insan Easy'sinde kick payı yalnızca 0,053), ilk 30 sn nota/sn 2,77 → 2,30, en uzun kick-snare dizisi ilk 30 sn 10 → 5; şarkı boyu 21'lik dizi kaldı (152-158 sn): oradaki kick'ler Expert'te tek başına kick, kural onlara dokunmuyor. Hard ve Medium aynı.
- **`train` sonucu** (artımlı; `train_karsilastirma_5.md`, ortalama): gitar Hard nota F1 0,703 → 0,718 (P 0,799 → 0,755, R 0,649 → 0,709; RHCP dışı 0,701 → 0,727), yoğunluk insan Hard'ının 0,841'i → 0,981'i, Expert'e oran 0,662 → 0,776 (insan 0,735), yön 0,342 → 0,341, en kötü şerit farkı 0,156 → 0,160; gitar Medium ve Easy aynı. Bas Hard aynı (0,796); bas Medium nota F1 0,744 → 0,785 (P 0,855 → 0,863, R 0,672 → 0,729), yoğunluk 0,789 → 0,847, oran 0,381 → 0,410 (insan 0,526), yön 0,755 → 0,737, en kötü şerit farkı 0,139 → 0,155; bas Easy 0,745 → 0,744.
- **Kabul kriterleri.** Tuttu: üç enstrümanda Expert aynı; gitar Hard F1 düşmedi; bas Hard ve Medium F1'i −0,01'den fazla düşmedi, Medium'un yoğunluğu insana yaklaştı; 5c'de 150 BPM ve altı bayt bayt aynı, First Date Easy konum F1 −0,004, Zombiler'in en uzun kesintisiz kick-snare dizisi ilk 30 sn 25 → 5, şarkı boyu 61 → 17; Californication bas alt sınırları (Hard 0,774 ≥ 0,77, Medium 0,771 ≥ 0,76, Easy 0,649 ≥ 0,64, yön, şerit farkı, "önce vuruşlar"dan iyi); oynanabilirlik: her seviyenin en kısa aralığı `train` insanlarının o seviyedeki en kısasının üstünde (gitar Hard 0,077 / Medium 0,229, bas Hard 0,104 / Medium 0,154 sn; bizim en kısa: gitar Hard 0,150, Medium 0,300, bas Medium 0,314), şarkı başına da 5. adım yeni bir ihlal getirmedi (gitar Hard Scar Tissue 0,154 < insan 0,166 ve bas Medium Parallel Universe 0,406 < 0,439 önceden de öyleydi). Tutmadı: gitar Hard F1'inin belirgin yükselmesi (+0,015; proje sahibinin hedefi); bas Hard'ın yoğunluğu (değişmedi). **Californication'da 0,02'den fazla kötüleşen (onay gerekiyor):** gitar Hard nota P 0,763 → 0,722 (F1 0,734 → 0,759), gitar Hard sustain payı 0,246 → 0,206 (insan 0,256).
- **Test seti (ayarlar dondurulduktan sonra bir kez, 2026-11-16; `test_karsilastirma.md`, `test_5c.md`; "önce" 4. adımın B ölçümü, aynı kod; dondurma anındaki dosya hash'leri `dondurma.txt`):** gitar Hard F1 0,586 → 0,629 (Queen ve 1981 hariç 0,713 → 0,742; 1981 0,609 → 0,688, Otherside 0,731 → 0,765, Kids 0,695 → 0,718, We Will Rock You 0,310 → 0,344), Hard yön 0,263 → 0,251; bas Medium F1 0,497 → 0,589 (hariç 0,599 → 0,700; Kids 0,523 → 0,702, 1981 0,408 → 0,554), yön 0,635 → 0,599; bas Hard ve davul Expert/Hard/Medium aynı. Davul Easy konum F1 0,811 → 0,799. **1981** (185 BPM): Easy konum F1 0,617 → 0,573, kick F1 0,651 → 0,545, en uzun kick-snare dizisi ilk 30 sn 9 → 5, şarkı boyu 9 → 7; insan Easy'si bizimkinden çok seyrek (1,42 nota/sn, bizim 2,69 → 2,56) ve kick'leri tutuyor (kick payı 0,435): R1 bu şarkıda insandan uzaklaştırdı. **Kids** (206,7 BPM): Easy konum F1 0,919 → 0,916, kick F1 0,129 → 0,143, en uzun dizi 9 → 3. Otherside ve We Will Rock You (≤ 129 BPM) değişmedi.
- **Gerçek dışı örnekler** (`gercek_disi_5.md`; önce: d1de7f0 ile `outputs\<şarkı>`, sonra: `derlemeler_sonra\`; beşi de validator'dan geçti; Expert'ler aynı): gitar Hard LastResort 437 → 522, Şarkı Testi 384 → 458, Zombiler 405 → 484 konum (Expert'in ~%80'i). Bas Medium LastResort (181 BPM) 232 → 365 (1,21 → 1,91 nota/sn, en kısa aralık 0,405 → 0,331 sn), Zombiler 262 → 403, Danza 315 → 336, Toca 129 → 137; Şarkı Testi'nin bası aynı. Davul Easy yalnızca Zombiler'de (426 → 350; ilk 30 sn 2,1 → 1,7 nota/sn, kick payı 0,342 → 0,219) ve LastResort'ta (413 → 411) değişti.
- **Onay bekleyen sabit testler** (yeni değerler testlere yazıldı ki `-Full` koşabilsin; eskileri yorumda, onaylanmazsa geri alınır): gitar hash'i LastResort `737bc3b8…` → `1f9259b1…`, Şarkı Testi `0350be9a…` → `4c1545f3…` (yalnızca Hard); bas hash'i Danza `84a128a0…` → `ee648232…`, Toca `e6d75583…` → `c297d4ae…`, LastResort `4d1f34ac…` → `05dcee04…` (Medium ve onu izleyen Easy; Şarkı Testi'nin bas hash'i aynı); dosya hash'leri `difficulty.toml` `587c38ca…` → `7683e6e2…`, `bass_difficulty.toml` `5fd616e5…` → `10c5e5c3…`; `test_bass_hard_and_medium_count_beats_as_well_as_seconds` (Medium `min_gap_beats` None → 1.0), `test_bad_configuration_is_refused` (aranan satır 0.67 → 0.80). Yeni: `tests/test_fast_easy_drums.py` (9 test).

**Sonra 1: bölümler (2026-11-16; plan ve sonuç onaylandı; `-Full` 1105 test, 820 sn; commit edildi; SPEC 46).** Proje sahibinin yönergesi: en kısa bölüm ve pencere ölçü yerine saniyeyle ya da 150 BPM ilkesiyle sınırlansın.
- **Bugün** (`train`, 1. adımdan beri değişmedi): değişim penceresi (`kernel_bars`) 8 ölçü, en kısa bölüm 4 ölçü; ikisi de ölçüyle sayılıyor, yani hızlı şarkıda saniyece kısalıyor (207 BPM'de 9,3 sn / 4,6 sn). `train`'de 150 BPM üstünde tek şarkı var ve orada fazla değil **az** bölüyoruz: First Date 11 bölüm, insan 15, sınır F1 0,538 (1. adımdan önce, yarı tempoda 9 bölüm, 0,583). Öteki 7 şarkı ≤ 146,5 BPM. Gerçek dışı: LastResort (181 BPM) 12 bölüm (1. adımdan önce 11), Zombiler (183) 9. Fazla bölme yalnızca test setinde görüldü (Kids 31 / 10, 1. adımın raporu). `train` insanlarının en kısa bölümü 6,5 sn (Holiday, 4 ölçü); 150 BPM'de 4 ölçü 6,4 sn.
- **Seçenek B1 (önerilen; SPEC 41'in bölümlere uygulanması):** pencere ve en kısa bölüm yine ölçüyle sayılır ama saniyece 150 BPM'dekinden kısa olamaz: pencere ≥ 12,8 sn, en kısa bölüm ≥ 6,4 sn. 150 BPM ve altı bayt bayt aynı; 191 BPM'de pencere 11, en kısa bölüm 6 ölçü; 207 BPM'de 12 ve 6. Sürekli: 151 BPM'de neredeyse hiçbir şey değişmez.
- **Seçenek B2:** 150 BPM üstünde bölüm aramasında iki ölçü bir sayılır (yarı tempo ızgarası): 1. adımdan önceki davranışı geri getirir (First Date'te 9 bölüm, 0,583). Sıçramalı: 151 BPM'de pencere ve en kısa bölüm birden iki katına çıkar.
- **Saf saniye (önerilmiyor):** her tempoda sabit saniye; yavaş şarkıları da değiştirir, Californication'ın 0,70 eşiği riske girer.
- **Ölçüm (yalnızca `train`):** (1) First Date'in kendisi; (2) tempo oktavına dayanıklılık: öteki 7 `train` şarkısının tempo haritası yapay olarak iki katına çıkarılıp (her ölçü ikiye bölünür, ses aynı) bölümler bugünkü kural, B1 ve B2 ile yeniden bulunur; insan sınırlarıyla F1 ve bölüm sayısı, gerçek temposundaki sonuçla karşılaştırılır. Böylece "hızlı şarkıda kısa ölçü" durumu insan etiketli 7 şarkıda sınanır, test setine bakılmaz. Senin şarkıların (LastResort, Zombiler) dk:sn listesiyle alıştırma modu için verilir.
- **Önerilen kabul kriterleri:** 150 BPM ve altındaki şarkıların bölümleri bayt bayt aynı (7 `train` şarkısı, Danza, Toca, Şarkı Testi; Californication testleri kendiliğinden geçer); kesin kurallar (ölçü başı, en az 4 ölçü, ASCII ad) ve validator aynı; yapay iki kat tempoda seçilen kuralın ortalama sınır F1'i bugünkü kuraldan yüksek ve gerçek tempodakine yakın; First Date sınır F1'i en çok 0,05 düşer (0,538 → ≥ 0,488). Test seti adımın sonunda bir kez: Kids ve 1981'in bölüm sayısı ve F1'i ayrıca raporlanır; Otherside ve We Will Rock You (≤ 150 BPM) değişmemeli.
- **Kapsam dışı:** eşik (0,18), harf eşiği (0,6), özellik ağırlıkları, ardışık aynı harfli bölümleri birleştirme. Star power aralığı ve preview ayrı adımlar, sonra.
- **Proje sahibinin kararları (2026-11-16):** (1) B1 ve B2 `train`'de (First Date + yapay iki kat tempo) ölçülür, kabul kriterlerine göre seçilir; eşitlikte B1 (değişim sürekli). (2) First Date için en çok 0,05 düşüş uygun. (3) Onay sonda tek seferde, artımlı tabloyla. Kabul kriterleri ve kapsam önerildiği gibi. Bitince: test setinin tek ölçümü (Kids ve 1981 ayrıca), LastResort ve Zombiler'in bölüm listesi (dk:sn), değişen testler, `-Full` komutu.
- **Motor:** `outputs\_experiments\adim6_bolum\motor6.py` (her `train` şarkısının kare özellikleri ve tempo analizi bir kez; `find_sections`'ı kurala göre yeniden yürütüyor; puan hep gerçek haritanın ölçüleriyle; `verify`: bugünkü kural 8/8 `find_sections`'la ve `train` raporuyla aynı). `olc_6.md`, `faz_6.log`, `dogrula_6.log`.
- **`train` sonucu:** 150 BPM ve altındaki 7 şarkıda B1 ve B2 bugünküyle aynı. First Date: bugün 0,538 (11 bölüm, insan 15), B1 0,455 (7), B2 ölçüleri haritanın ilk ölçüsünden çiftleyince 0,250 (9; sınırlar bir ölçü kayık). Yapay iki kat tempoda (7 şarkı): bugün 0,581 ve 19,7 bölüm (Holiday 35, Parallel Universe 34; insan ortalaması 15,4; gerçek tempoda 0,676), B1 0,595 / 12,3, B2 0,676 / 13,1 (yapay haritada çiftler kurgu gereği doğru). **Çiftleme fazı:** çiftler şarkının ilk sesli ölçüsünden sayılınca (ilk bölüm zaten orada başlıyor; yarı tempoda o ölçü bir ölçü başı olurdu) First Date 0,583 (9 bölüm; 1. adımdan önceki değer), yapay iki kat 0,682 / 13,3.
- **Seçim: B2, ilk sesli ölçüden çiftleme** (`sections.py`: ortanca tempo `FLOOR_BPM`'in üstündeyse `bar_step = 2`; `analysis.json` `sections.bar_step`; terminalde bir satır; SPEC 46). Kabul kriterleri: 150 BPM ve altı bayt bayt aynı ✓, kesin kurallar ve validator aynı ✓, yapay iki kat tempoda F1 bugünden yüksek ve gerçek tempoya yakın (0,682 / 0,676) ✓, First Date en çok −0,05 (+0,045) ✓. B1 First Date kriterini tutmadı (−0,083), eşitlik yok. Proje kodu motorla aynı sonucu veriyor (`dogrula_6.py`, `find_sections`'ın kendisi).
- **Test seti (ayarlar dondurulduktan sonra bir kez; `test_bolum.md`, `test_karsilastirma.md`; "önce" 5. adımın ölçümü, aynı kod; `dondurma.txt`):** Kids (199,5 BPM) 31 → 8 bölüm (insan 10), medyan bölüm 4,8 → 19,2 sn (insan 19,2), sınır F1 0,488 → 0,444 (P 0,32 → 0,50, R 1,0 → 0,4). 1981 (185 BPM) 8 → 6 bölüm (insan 11, ~10,4 sn'lik bölümler), F1 0,526 → 0,353: çiftlenmiş 8'lik pencere (~21 sn) bu kısa bölümleri görmüyor. Otherside ve We Will Rock You aynı ✓. Test ortalaması 0,433 → 0,379; bölüm sayısı bizim / insan 1,28 → 0,66.
- **Gerçek dışı örnekler** (`gercek_disi_6.md`; altısı validator'dan geçti; enstrüman chart'ları hiçbir şarkıda değişmedi): LastResort (181 BPM, `bar_step` 2) 12 → 11 bölüm, en kısa 4,9 → 10,3 sn; yeni liste 1. adımdan önce (yarı tempoda) alıştırma modunda bakılan listeyle aynı. Zombiler (183) 9 → 9, sınırlar değişti (ilk bölüm 0:00-0:49,5). Preview bölümlerden seçildiği için değişti: LastResort 1:12,6 → 2:17,5, Zombiler 2:49,7 → 0:49,5. Danza, Toca, Şarkı Testi bayt bayt aynı (`bar_step` 1).
- **Değişen testler:** `test_analysis_records_the_whole_build` (`analysis.json`'un `sections` anahtarlarına `bar_step` eklendi). Yeni (`tests/test_sections.py`): iki kat tempoda okunan şarkı aynı bölümleri alıyor; 150 BPM'de çiftleme yok, 151'de var; çiftler ilk sesli ölçüden başlıyor (haritanın ilk ölçüsünden çiftleme her sınırı bir ölçü kaydırırdı, bu test onu yakalıyor). Hash'ler değişmedi (gitar ve bas hash'leri `[Events]`'i kapsamıyor).
- **Açık konu (2026-11-16):** hızlı punk şarkılarında (1981) insan ~8 ölçülük (~10 sn) bölümler kullanıyor; çiftlenmiş pencere bunları kaçırıyor. Pencereyi saniyeyle ayarlamak ileride denenebilir; bu adımda test setine bakıldıktan sonra değişiklik yok.

**Sonra 3: preview P1 (2026-11-16; plan onaylandı, sonuç uygulanmadı; branch `preview-p1`, `11ef55d`).**
- **Kural (branch'te):** en gürültülü tekrar eden harfin ilk görünüşü (şarkının ilk bölümünden en az 16 ölçü sonraysa; değilse ikincisi), ondan 14 sn önceki en yakın ölçü çizgisi; `evaluate` "pencerede insan nakaratı başlıyor mu"yu ölçüyor. Seçim `train`'de proje sahibinin sırasıyla (nakarat isabeti → ortanca uzaklık → konum).
- **`train`:** nakarat isabeti 6/8 → 7/8 (insanın kendisi 8/8), insan preview'una ortanca uzaklık 34,1 → 17,4 sn, ilk notadan sonra ortanca 95,2 → 58,5 sn (insan 38,7); Californication 0,2 → 94,0 sn uzak (insan ikinci nakaratı seçmiş).
- **Test seti (bir kez):** nakarat isabeti 2/4 → 1/4, ortanca uzaklık 68,7 → 68,4 sn; Kids (199 BPM) 78,8 sn (insandan 1,1 sn) → 11,4 sn, girişte; Otherside'ın penceresi bir nakaratın içinde başlıyor.
- **Proje sahibinin şarkıları (yalnızca `preview_start_time` değişmişti):** Mor ve Ötesi 1:45.1 → 0:34.5, LastResort 2:17.5 → 0:27.6, Danza 2:41.8 → 1:05.7, Toca 1:35.5 → 0:25.1; Zombiler ve Şarkı Testi yedek kuralda, aynı.
- **Karar (2026-11-16):** şimdilik uygulanmıyor, eski sistem kalıyor; "Yapılacak / kontrol edilecek" listesinde. Deneyler ve raporlar `outputs\_experiments\adim8_preview\` (motor, tarama, `train_karsilastirma_8.md`, `test_pv.md`, `gercek_disi_8.md`, derlemeler). Test seti notu: plan için veri ararken 7. adımın test raporunda test setinin şarkı başına preview değerleri görülmüştü; tasarımda kullanılmadı.

**Sonra 2: star power aralığı (2026-11-16; plan ve sonuç onaylandı; `-Full` 1108 test, 1102 sn; commit edildi; SPEC 47).**
- **Bugün** (D.3, yalnızca Californication'a göre): ifade 1 ölçü; ilki şarkı başladıktan ~15 sn sonra, sonrakiler ~25 sn arayla (20-30 sn), Easy'de en az 2 notalı ölçüler önce; dakikada 1,5-3 yumuşak hedef. `train`'de bizim ifade sayımız insanınkinin ~0,83'ü, aralığımız her şarkıda ~25 sn.
- **`train` insanları** (`train_sonrasi.json`, 8 şarkı, gitar/bas/davul): aralık saniye olarak 11-29 sn ama **ölçü olarak ~8-10** (ortanca ~9): First Date (191 BPM) 11-12 sn = 9-10 ölçü, Californication (97) 22-29 sn = 9-12 ölçü, In Too Deep 18-23 sn = 8-11 ölçü. Sapanlar Dani (5-6 ölçü) ve Fat Lip (topluluk chart'ı, 4,7-7,6 ölçü, ifadelerin çoğu ölçü başında değil). İfade uzunluğu ortanca 1 ölçü. Dakikada 1,9-4,2 ifade. İlk ifade şarkı başladıktan 2-12 ölçü (8-28 sn) sonra. Bizim 25 sn kuralı hızlı şarkıda çok seyrek: First Date'te insan 11-12, biz 6. İnsan ifadeleri insan bölümlerine bağlı değil: bölüm başından uzaklık 0'dan 8+ ölçüye yayılmış (en sık 3 ve 7), ~%24'ü bir sonraki bölümden hemen önceki ölçüde.
- **Öneri:** aralık saniye yerine ölçüyle: hedef `gap_bars` (~9, `train` insan ortancası), izinli aralık ölçüyle (ör. 6-12), ilk ifade ölçüyle (`first_after_bars`, `train` ortancası); dakikadaki ifade yumuşak hedefi `train` insan aralığından. İfade 1 ölçü, Easy'de en az 2 notalı ölçü tercihi, dört seviyede aynı yer ve bütün kesin kurallar aynı. Değerler `train`'de taranır (`gap_bars` 7-11, aralık genişliği), seçim: ifade sayısı oranı (bizim / insan) 1'e en yakın ve aralığın ölçü ortancası insanınkine yakın; ifadelerin insan ifadelerine ±1 ölçü denk gelmesi yalnızca teşhis olarak raporlanır.
- **150 BPM tabanı önerilmiyor:** 9 ölçüye 150 BPM'deki saniye tabanı (~14 sn) First Date'te insanın 11 sn'lik aralığına ters düşer.
- **Önerilen kabul kriterleri:** nota satırları bayt bayt aynı, yalnızca `S 2` satırları değişir; kesin kurallar ve validator aynı; `train`'de üç enstrümanda ifade sayısı oranının ortalaması bugünkünden (~0,83) 1'e daha yakın; şarkı başına aralığın ölçü ortancası 6-12 ölçü içinde; Easy'de 2'den az notalı ifade bugünkünden fazla değil. Californication testi (`test_californication_star_power_is_spaced_like_the_human_charts`) sayı ve dakika şartlarını korur, ama "aralıklar 20-30 sn" şartı eski kuralın kendisi (insanın değil): ölçüyle yazılması onaya sunulur. Test seti adımın sonunda bir kez; senin şarkılarının ifade sayısı ve aralıkları raporlanır.
- **Kapsam dışı:** ifade uzunluğu (1 ölçü kalır), davul fill'i ve davulda açılış (oyunda doğrulanmadı), ifadeleri bölümlere bağlamak (insan verisi desteklemiyor).
- **Proje sahibinin kararları (2026-11-16):** (1) aralık ölçüyle (hedef ~9, izinli aralık ölçüyle), değerler `train`'de taranıp önerilen ölçütlerle seçilir; ilk ifadenin yeri de ölçüyle. (2) 150 BPM tabanı yok. (3) Onay sonda tek seferde, artımlı tabloyla. Kabul kriterleri ve kapsam önerildiği gibi; Californication star power testinin ölçüyle yeniden yazılması sonda onaya sunulur. Bitince: test setinin tek ölçümü; Zombiler, LastResort, Danza, Toca ve Mor ve Ötesi'nin ifade sayıları ve aralıkları; `-Full` komutu.
- **Motor:** `outputs\_experiments\adim7_starpower\motor7.py` (`train`'in 8 şarkısında gitar, bas ve davulun dört seviyesi `evaluate`'teki gibi bir kez; insan ifadeleri ve ölçüleri yanında; yerleştirme bugünkü kuralla ya da ölçüyle). Teşhis ve tarama `tarama_7.log`, `tarama_7b.log`, sonuç `train_karsilastirma_7.md`; proje kodu motorla 24/24 aynı (`dogrula_7.log`).
- **Tarama (yalnızca `train`):** hedef 7-11 ölçü, pencere ±2 ve ±3, ilk ifade 4/6/8 ve sonra `train` ortancası 9 ölçü. 9 ölçü aralık ortancasını insanınkiyle tutturuyor (9 / 9) ama %13 fazla ifade koyuyor (insan bazı kısımları, giriş ya da solo gibi, boş bırakıyor); 10 ölçü ifade sayısını eşitliyor (ortalama oran 0,99-1,02), aralık ortancası 10 / 9; 11 ölçü şarkı başına sapmada biraz daha iyi (0,13 / 0,16) ama ortalama oran 0,91 ve aralık 11 / 9. **Seçilen: hedef 10, 7-13, ilk ifade 9 ölçü sonra** (`star_power.toml`; SPEC 47). Dakikadaki ifade yumuşak hedefi 1,5-4,5 (`train` insanları 1,9-4,2).
- **`train` sonucu** (bugün → seçilen): ifade sayısı oranı ortalaması gitar 0,824 → 1,016, bas 0,833 → 1,018, davul 0,828 → 0,963; |oran − 1| 0,207/0,203/0,289 → 0,141/0,162/0,184; aralığın ölçü ortancası her şarkıda 9-10 (bugün 9-20; 6-12 dışı 10 şarkı-enstrüman → 0); Easy'de 2'den az notalı ifade toplam 3 → 3 (gitar 2 → 3, davul 1 → 0); ±1 ölçü denk gelme (teşhis) 0,175 → 0,175. First Date 6 → 12-13 (insan 11-12), Californication gitar 13 (13), bas 13 (12), davul 13 (11). Dani (insan 5-6 ölçü) ve Fat Lip davulu (6,5) bu kuraldan sık: 11 ve 7'ye karşı 17-19 ve 13.
- **Kabul kriterleri:** nota satırları bayt bayt aynı, yalnızca `S 2` değişiyor ✓ (yedi gerçek dışı derlemede `S 2` dışında `notes.chart` ve `song.ini` aynı); kesin kurallar ve validator aynı ✓; oran ortalaması üç enstrümanda 1'e daha yakın ✓; aralığın ölçü ortancası 6-12 içinde ✓; Easy'de seyrek ifade toplamı artmadı ✓ (gitarda +1).
- **Test seti (ayarlar dondurulduktan sonra bir kez; `test_sp.md`, `test_karsilastirma.md`; yalnızca star power değişti; `dondurma.txt`):** ortalama oran 0,778 → 1,131, |oran − 1| 0,222 → 0,198. Kids (199,5 BPM) 7 → 15-16 (insan 13-14), aralık ortancası 25 → 12,0 sn (insan 10,8-12,0); 1981 (185) 5-6 → 10-11 (insan 7-8): fazla; Otherside 10 → 13 (insan 10-12); We Will Rock You (81,65) 5 → 4-5 (insan 5).
- **Gerçek dışı örnekler** (`gercek_disi_7.md`; yedisi validator'dan geçti): Mor ve Ötesi (119 BPM) 8 → 9-10, Zombiler (183) 8 → 16-17 (dakikada 4,6-4,9, yumuşak hedefin üstünde, uyarıyor; Easy'de seyrek ifade gitar 3, davul 2, bas 1), LastResort (181) 8 → 15-16 (4,5-4,8), Danza 8 → 10-11, Toca 6-7 → 8-9, Şarkı Testi 7-8 → 8-9, Tempo Test 8 → 15.
- **Değişen testler (onaya sunuldu):** `test_californication_star_power_is_spaced_like_the_human_charts`: "aralıklar 20-30 sn" şartı (eski kuralın kendisi) yerine "aralıklar 7-13 ölçü"; sayı (insandan en çok 2 farklı) ve dakika şartı kalıyor, dakika aralığı artık 1,5-4,5. Eski şartla geçmezdi: bas ve davulda 8 ölçülük 19,9 ve 19,6 sn'lik birer aralık var. `tests/test_star_power.py`: yerleştirme testleri ölçüyle (120 BPM'de ilk ifade 18 sn, sonra 20 sn arayla), uzun aralık uyarısı ölçüyle, ayar dosyası testleri yeni anahtarlarla (+ tam sayı ve `bars <= min_gap_bars` reddi), onaylı ayarlar testi (9, 10, 7, 13; dakika 1,5-4,5).
- **Açık konu:** hızlı punk şarkılarında (1981) insan daha seyrek koyuyor; kural şarkı stiline bakmıyor. Dani ve Fat Lip'in davulu daha sık.

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

## D.3: star power

**Proje sahibinin kararları (2026-11-15):** star power dört enstrümanda planlandığı gibi: ifade başına 1 ölçü, ~20-30 sn'de bir, bir enstrümanın dört seviyesinde aynı yerde. İfadelerin oyunda doğru göründüğü bot denemesinde doğrulandı. Davul fill'i (`S 64`) şimdilik yazılmıyor; davulda star power'ın nasıl açıldığı "oyunda doğrulanmadı" olarak burada ve `analysis.json`'da yazılı. Davul deneyini proje sahibi şimdilik atladı, deney klasörü ileride test için duruyor. Validator star power kurallarını kendi başına denetliyor.

**Nasıl yerleştiriliyor** (`chart/star_power.py`, ayarlar `chart/star_power.toml`, SPEC 40. karar):
- Her enstrüman kendi notalarına göre, ayrı ayrı. Aday ölçüler: şarkı başladıktan sonraki (`Song`'dan sonra), enstrümanın dört seviyesinin her birinde en az bir nota olan ölçüler.
- İlk ifade şarkı başladıktan ~15 sn sonraki en yakın aday ölçüde; her sonraki öncekinden 25 sn sonraya en yakın aday ölçüde, 20-30 sn aralığında. Easy'de en az 2 nota olan ölçüler önce gelir (Californication'ın insan chart'ında her ifadenin Easy'sinde en az 2 nota var). Aralıkta aday yoksa 20 sn'den sonraki ilk aday alınır ve uzun aralık uyarılır.
- İfade 1 ölçü; ölçü değişen şarkıda o ölçünün kendi uzunluğu.
- **Kesin kurallar kodda** (`check_star_power`) ve **validator'da** (`notes.chart`'tan, kendi başına): ifade ölçü başında başlar, ifadeler çakışmaz, her ifadede (kodda: enstrümanın her seviyesinde; validator'da: yazıldığı bölümde) en az bir nota var, hiçbir ifade şarkı başlamadan (`Song`'dan önce) başlamaz. `star_power.toml` bunları gevşetemez; bilinmeyen anahtar reddediliyor.
- **Yumuşak hedefler** (uyarı, terminal ve `analysis.json`): dakikada 1,5-3 ifade, 30 sn'den uzun aralık yok, Easy'de en az 2 nota.
- Terminal: `star power: guitar 8 phrases, 2.4 per minute, 21.2-29.1 s apart (median 26.5 s), fewest notes inside on Easy 1`; davulda sonuna `activation without fills not verified in the game`. `analysis.json`'da `star_power`: her enstrümanın ifadeleri (tick, süre, her seviyede içindeki nota sayısı), sayı, dakikadaki ifade, aralıklar, kesin kurallar ve `not_verified_in_game` (davul chart'lanınca: fill yazılmadığı ve açılışın oyunda denetlenmediği).
- `evaluate` bizim star power'ımızı da insanınkiyle aynı ölçülerle yazıyor (`star power, mine`).

**Californication** (`train`, ayarlar insan chart'ına bakarak seçildi):

| | İnsan | Bizim |
|---|---|---|
| Gitar | 13 ifade, 2,41/dk, aralık ortanca 22,4 sn, içinde en az 4 nota (Expert) | 12 ifade, 2,22/dk, 24,9 sn, en az 4 |
| Bas | 12, 2,22/dk, 26,8 sn, en az 5 | 12, 2,22/dk, 25,2 sn, en az 4 |
| Davul | 11, 2,04/dk, 28,6 sn, en az 10 | 13, 2,41/dk, 24,8 sn, en az 8 |
| Keys | 1 | yok (piyano stem'i yok) |

Hepsi ölçü başında, 1 ölçü. Bizim bütün aralıklar 20-30 sn içinde (insanınkiler 12,3-44,5 sn). Easy'de 2'den az nota tutan ifade: gitarda 1 (11.'si), bas ve davulda yok; insan chart'ında yok. Test bunları sabitliyor (`test_californication_star_power_is_spaced_like_the_human_charts`: sayı insanınkinden en çok 2 farklı, dakikada 1,5-3, aralıklar 20-30 sn, Easy'de seyrek ifade gitarda en çok 1).

**Gerçek şarkılar** (yeniden derlendi, `Songs`'a kopyalandı):

| Şarkı | Enstrüman | İfade | Dakikada | Aralık (ortanca) | Easy'de en az | Uyarı |
|---|---|---|---|---|---|---|
| Danza | bas | 8 | 2,0 | 22,2-25,9 (25,9) | 2 | – |
| | davul | 8 | 2,0 | 22,2-25,9 (25,9) | 4 | – |
| Toca | bas | 6 | 2,2 | 24,8-28,6 (26,7) | 2 | – |
| | davul | 7 | 2,5 | 21,0-24,8 (24,8) | 3 | – |
| Davul Testi - LastResort | gitar | 8 | 2,4 | 21,2-29,1 (26,5) | 1 | 1 ifade Easy'de tek nota |
| | bas | 8 | 2,4 | 23,8-23,9 (23,8) | 2 | – |
| | davul | 8 | 2,4 | 23,8-23,9 (23,8) | 4 | – |
| Yerel Test - Şarkı Testi | gitar | 7 | 2,1 | 22,2-32,1 (24,7) | 1 | 1 aralık 32,1 sn; 1 ifade Easy'de tek nota |
| | bas | 8 | 2,4 | 22,3-27,2 (24,7) | 2 | – |
| | davul | 8 | 2,4 | 24,6-24,8 (24,7) | 2 | – |

Danza'nın girişli olduğu (`Song` 0:37.1) hesaba katıldı: ilk ifadesi 0:52.6'da.

**Bayt bayt aynı:** dört şarkıda `notes.chart`'ın `S 2` dışındaki bütün satırları ve `song.ini` önceki derlemeyle aynı (`outputs\_experiments\d3_compare_builds.py`); yalnızca her seviyeye aynı `S 2` satırları eklendi. Dördü validator'dan geçti. `Songs`'a yalnızca `notes.chart`, `song.ini` ve `analysis.json` kopyalandı (ses dosyaları değişmedi, dosya kümeleri aynı); `Songs`'taki hâlleri validator'dan geçti. Önceki üç dosya `outputs\_songs_backup\2026-11-15_d3\` altında. Oyun kapalıyken yazıldı.

**Oyun (bot):**
- `Davul Testi - LastResort` üç botla (`--player Guitar,Expert --player Bass,Expert --player ProDrums,Expert -i`): Lead Guitar, Bass Guitar ve Pro Drums otoyollarında star power notaları aynı anda, beklenen yerde camgöbeği çerçeveli görünüyor (`outputs\_experiments\d3_sp_deneyi\bot_lastresort\screen_024.0s.jpg`, ızgara `sheet_lastresort.jpg`).
- Keys oyunda görülmedi: hiçbir şarkıda piyano stem'i yok (yalnızca sentetik test).
- Bot star power'ı hiç açmıyor ve bot görünümünde oyuncunun star power ölçeri gösterilmiyor; ölçerin dolduğu ve açılış botla görülemiyor.

**Davulda star power'ın açılışı: oyunda doğrulanmadı.** Fill (`S 64`) yazılmıyor. Web kaynakları ve oyunun kılavuzu fill'siz chart'ta davulda star power'ın nasıl açıldığını söylemiyor (`S 64` = davul star power açma bölümü). Bot denemesinde (aşağıda) bot açmadı ve Hard'daki fill'ler görünmedi; botun ölçeri görünmediği için nedeni bilinmiyor. Proje sahibi deneyi şimdilik atladı.

**Star power tuşu (2026-11-15).** Oyunun kayıtlı tuş eşlemesi (kayıt defteri, Rewired `Player1` klavye haritası) okundu: Kırmızı `S` ve `H` (davulda `H` snare), Select/Star Power yalnızca `Return`. `H` star power'a bağlı değil, çakışma yok. Proje sahibi gitarda star power'ı `H` sanıyordu; Clone Hero'nun varsayılan klavye düzeni (kılavuz: "Select/Star Power - H") öyle, bu makinedeki kayıtlı düzen değil. Oyun açıkken Controls ekranında bir kez daha bakılacak. Diğer tuşlar: Yeşil `A`/`O`, Sarı `D`/`U`, Mavi `F`/`I`, Turuncu `G`/`B` (davulda kick), Sarı/Mavi/Yeşil zil `J`/`K`/`L`, Open `Space`, Whammy `;`, Start `RightShift`.

**Deney `SP Deneyi - Davul`** (`outputs\_experiments\d3_sp_deneyi\`, `sp_experiment.py` ile `Davul Testi - LastResort`'tan): yalnızca Pro Drums. Expert'te yalnızca star power ifadeleri (`S 2`, 1 ölçü, her 4 ölçüde bir; ilkleri 0:13.0, 0:23.6, 0:34.2, 0:44.8), fill yok. Hard'da aynı ifadeler ve her ikinci ifadeden hemen sonra 2 ölçülük `S 64` fill (0:26.3-0:31.6, 0:47.5-0:52.8, 1:08.7-1:14.0, 1:29.9-1:35.2), fill'in son tick'inde bir nota var.

**Bot denemesi (2026-11-15, D.2 commit'inden sonra).** `SP Deneyi - Davul` `Songs`'a kopyalandı; oyun iki botla yan yana açıldı (`--player ProDrums,Expert --player ProDrums,Hard -i`), 117 sn boyunca 1,5 sn'de bir ekran görüntüsü alındı (`outputs\_experiments\d3_sp_deneyi\bot_run.ps1`, kareler `bot_run_2\`, özet ızgaralar `sheet_2_*.jpg`). Şarkı açılıştan ~10 sn sonra başlıyor.
- Star power ifadeleri görünüyor: notalar beklenen anlarda (her ~10,6 sn) camgöbeği vurgulu, iki seviyede de.
- **Bot star power'ı açmadı:** otoyol hiçbir karede star power rengine dönmedi.
- **Hard'da fill görünmedi:** fill anlarında (0:26.3, 0:47.5, 1:08.7, 1:29.9) sağdaki otoyolda normal notalar var, boş/serbest bölge yok.
- Bot görünümünde oyuncu başına çarpan ve star power ölçeri gösterilmiyor; skor panelindeki mavi çubuk şarkının ilerleyişi (düzgünce doluyor), turuncu çubuk yıldız ilerlemesi. Yani botun ölçerinin yarıyı geçip geçmediği, fill'in bu yüzden mi gösterilmediği bilinmiyor.
- Sonuç: davulda star power'ın nasıl açıldığı bot modunda doğrulanamıyor. Proje sahibi Expert ve Hard'ı kontrol listesiyle çalacak. Controls ekranı oyunda açılmadı; tuşlar kayıt defterinden (`Return` = Select/Star Power).

**Proje sahibi çalarken neye bakacak** (`SP Deneyi - Davul`, Pro Drums; star power tuşu `Return`):
- Expert (fill yok): 0:13 ve 0:23.6'daki parlayan notaları hatasız vur (ölçer yarıya dolar; kaçarsa 0:34.2, 0:44.8). Sonra: notaların kaybolduğu, sonunda tek nota olan bir bölge (fill) çıkıyor mu; `Return` star power'ı açıyor mu; açmazsa sarı ve mavi zile birlikte vurmak (`J` + `K`) açıyor mu.
- Hard (fill var): aynı iki ifade; fill'ler 0:26.3, 0:47.5, 1:08.7, 1:29.9'da (~5 sn). İlki ölçer dolar dolmaz başladığı için gösterilmeyebilir. Fill sırasında notalar mı var yoksa boş bölge mi; sondaki notaya vurunca star power açılıyor mu; `Return` fill dışında da açıyor mu.

**Değişen testler** (tolerans gevşetilmedi):
- `test_evaluate_reports_the_structure`: `star_power.mine` boş bekleniyordu (D.0'da bizim star power yoktu); artık `evaluate` bizimkini ölçüyor: gitar 1 ifade, 1 ölçü, ölçü başında, rapor satırı `star power, mine: guitar 1 (`.
- `test_a_build_charts_drums_says_what_is_not_verified_and_writes_listening_files`: yalnızca yeni denetimler (`not_verified_in_game`, `S 64` yok).
- Yeni: `tests/test_star_power.py` (30 test: yerleştirme, ölçü değişimi, şarkı başlangıcı, seyrek seviye, uzun aralık uyarısı, ayarlar, kodda kesin kurallar, validator kuralları, `S 64` star power sayılmıyor, build'de dört seviyede aynı ifadeler, Californication).

**Kontroller:** `scripts\check.ps1 -Mid` geçti (2026-11-15): 1001 test, 315 sn, 8 klasör validator'dan geçti (yeniden derlenen dört şarkı star power'lı). Californication testi (`real`) ayrıca geçti. `-Full` proje sahibinin penceresinde geçti: 1022 test, 600 sn, 8 klasör validator'dan geçti.

## D.2: preview noktası

**Nasıl seçiliyor** (`chart/preview.py`, SPEC 39. karar):
- Bölümlerden tekrar eden harfler (`Song`'un kısmı da harfinin ilki sayılıyor) karışımın ses düzeyine göre sıralanıyor: harfin bütün ölçüleri boyunca ortalama RMS, dB. En gürültülüsünün ikinci kez başladığı ölçüden 4 ölçü önce preview başlıyor.
- Tekrar eden harf ya da bölüm yoksa yedek kural: girişten sonraki en gürültülü 30 sn, en yakın ölçü çizgisine oturtuluyor. Build bunu uyarı olarak yazıyor (`preview: no part comes back, ...`).
- 30 sn şarkıya sığmıyorsa preview ölçü ölçü öne kayıyor; kaç ölçü kaydığı yazılıyor. Girişten sonra 30 sn'den kısa bir şarkıda preview şarkının ilk ölçüsünde başlıyor.
- **Kesin kurallar kodda** (`check_preview`): ölçü başında, `Song`'dan önce değil, 30 sn şarkıya sığıyor. **Validator kendi başına** (`notes.chart`'taki `Song` ve `song.ini`'den): preview `Song`'dan önce değil, şarkının sonunu geçmiyor, 30 sn sığıyor (şarkı `Song`'dan sonra 38 sn'den kısaysa sığma aranmıyor: 30 sn + en uzun ölçü 8 sn). `-1` ya da yazılmamış preview oyunun seçimi, denetlenmiyor.
- Terminal: `preview: 2:41.8, 4 bars before C2 (C is the loudest part that comes back, -12.2 dB)`. `analysis.json`'da `preview` kaydı: başlangıç, kural, hangi bölüme götürdüğü, tekrar eden harflerin ses düzeyi, yedek kuralın nedeni, kayma.
- `evaluate` aynı kuralı kullanıyor: `preview: mine 174.6 s (prechorus_2, 4 bars before F2), human 174.4 s (prechorus_2): 0.2 s apart`.

**Sonuçlar** (dk:sn; eski = en gürültülü pencere, D.1'e kadar):

| Şarkı | Preview | Kural | Götürdüğü bölüm | Tekrar eden harfler, dB | Eski |
|---|---|---|---|---|---|
| Californication (`train`, yalnızca `evaluate`) | 2:54.6 (174,6 sn) | tekrar | F2 3:04.5 (insanda chorus_2) | F -19,3, H -20,9, C -22,3, G -24,3, B -26,6 | 4:45.1 |
| Danza | 2:41.8 | tekrar | C2 2:49.1 | C -12,2, H -16,1 | 3:21.4 |
| Toca | 1:35.5 | tekrar | D2 1:43.2 | D -13,9 | 0:38.4 |
| Davul Testi - LastResort | 2:12.2 | tekrar | D2 2:22.8 | D -10,6 | 1:18.1 |
| Yerel Test - Şarkı Testi | 2:37.1 | yedek: tekrar eden bölüm yok | – | – | 2:37.0 |

- **Californication:** insanın preview'u 174,4 sn (ikinci nakarattan 4 ölçü önce). Bizimki 174,6 sn, fark 0,18 sn, ikisi de `prechorus_2`'de. En gürültülü tekrar eden harf F, insanın chorus_1 ve chorus_2'si. Eski kural 110,7 sn uzaktaydı.
- **Yedek kural** 5 şarkının 1'inde devreye girdi: Şarkı Testi'nin 8 bölümünden hiçbiri 0,6 eşiğinde tekrar etmiyor. Danza, Toca ve LastResort'ta en az bir harf tekrar ediyor. Toca ve LastResort'ta tek tekrar eden harf var (D), yani seçim "en gürültülü" değil "tek seçenek".
- Hiçbir şarkıda preview kaymadı (30 sn hepsinde sığıyor), hiçbiri girişte değil (girişli tek şarkı Danza; `Song` 0:37.1, preview 2:41.8).
- **Önerilen ölçüm kriteri** (proje sahibinin kararı bekleniyor, teste yazılmadı): Californication'da preview insanınkinden en çok 1 ölçü (yaklaşık 2,5 sn) uzakta. Testte bugün ölçülen değer (174,61 ± 0,05 sn), kural (F2'den 4 ölçü önce) ve insan bölümü (`prechorus_2`) sabit.

**Bayt bayt aynı:** dört şarkı yeniden derlendi. `notes.chart`'ın bütün `N` satırları ve `[SyncTrack]` önceki kopyalarla aynı. `song.ini`'de yalnızca `preview_start_time` değişti. `[Events]`'te: Danza'nın harfleri D.1'deki `Song` kararıyla değişti (10 satır, tick'ler aynı); Şarkı Testi ilk kez bölüm aldı (8 satır; önceki kopyası B fazından). Dördü validator'dan geçti.

**Oyun:** dört klasör `Songs`'a kopyalandı (`notes.chart`, `song.ini`, `analysis.json`, `.ogg`'ler) ve `Songs`'taki hâlleri de validator'dan geçti. Oyun kapalıyken yazıldı. Önceki kopyalar `outputs\_songs_backup\2026-11-12\` altında.
- **Şarkı Testi düzeltildi (2026-11-15).** D.2'de `--instruments guitar` ile derlenmişti: bas ve davul `song.ogg`'a gitmişti. Proje sahibi bunu beklenmedik buldu. Bulunanlar:
  - O derlemenin `notes.chart`'ında bas ve davul bölümü yoktu (`[ExpertSingle]`...`[EasySingle]` ve `diff_bass = -1`, `diff_drums = -1`). `Songs`'taki önceki kopyada (2026-11-08, Faz B) da yoktu: o zaman bas ve davul henüz chart'lanmıyordu (`analysis.json`: "chart generation is not implemented yet; audio only"), yalnızca sesleri ayrı dosyadaydı. Bas hash testleri bu şarkının basını `-Full`'da ayrıca derliyor; oyundaki kopyaya hiç girmemişti.
  - Varsayılan build dört enstrümanı da istiyor (`--instruments` verilmezse `guitar,bass,drums,keys`). Bir enstrümanı yalnızca stem varlık kontrolü dışarıda bırakıyor. `--instruments guitar` D.2'de elle verilmişti: önceki kopyada yalnızca gitar chart'ı olduğu için "önceki gibi" sanıldı. Kodda hata yok; varsayılanı sabitleyen bir test eklendi (`test_cli_build_asks_for_every_instrument_unless_told_otherwise`, varsayılan yalnızca gitar olunca başarısız olduğu denendi).
  - Varsayılanla yeniden derlendi: gitar, bas (4 seviye) ve Pro Drums (4 seviye). Keys yok: piyano stem'i eşiğin altında (-63,5 dB, %1 etkin). Ses dosyaları ayrı: `guitar.ogg`, `bass.ogg`, `drums.ogg`, `vocals.ogg`, `song.ogg` (other ve piyano). Gitarın bütün satırları, `[SyncTrack]` ve `[Events]` gitarlı derlemeyle aynı; `song.ini`'de `diff_bass = 2`, `diff_drums = 4`, `pro_drums = True`. Ses dosyalarının boyutları 2026-11-08 kopyasıyla aynı, ortak kazanç yeniden 1,0. Preview aynı (2:37.1, yedek kural).
  - `Songs`'a kopyalandı, `Songs`'taki hâli validator'dan geçti. Eski `debug_click.wav` duruyor: tempo haritası değişmediği için hâlâ doğru.
- **Yedekler** `outputs\_songs_backup\` altında: `2026-11-11\` (C.2 öncesi Danza ve Toca), `2026-11-12\` (D.2 öncesi dört şarkı), `2026-11-15\` (gitarlı Şarkı Testi). Temp'teki iki `songs_backup_*` klasörü buraya taşındı. `scripts\check.ps1` artık adı `_` ile başlayan klasörleri şarkı saymıyor, yoksa validator yedek klasörünü şarkı diye denetleyip başarısız olurdu.
- `Tempo Test - LastResort otomatik` (`Songs`'ta, gitar tempo testi) yeniden derlenmedi: preview'u eski (1:18.1).

**Preview'ları dinlerken neye bakmalı:** şarkı listesinde şarkının üstüne gelince preview çalıyor. Preview birkaç saniye sonra daha önce duyulmuş, şarkının en tanınır kısmına (çoğu zaman nakarat) giriyor mu? Başlangıcı bir cümlenin ortasında kalıyor mu? Şarkı Testi yedek kuralda, onda da en gürültülü kısım mı çalıyor? Not için şarkı ve "nakarat değil, şuradaki kısım olmalıydı (dk:sn)" yeterli.

**Sınırlar:**
- "En enerjik" = karışımın ses düzeyi. Yoğunluk (vuruş sayısı) ya da vokalin varlığı ölçülmüyor. Harfler tekrarların ancak bir kısmını yakaladığı için (D.1, %39) en gürültülü tekrar her zaman nakarat olmayabilir.
- Tek referanstan: kural Californication'da insanın preview'unu buluyor, başka insan preview'u yok.

**Değişen testler** (tolerans gevşetilmedi):
- `test_californication_structure_is_read_and_measured` (`-Full`): bizim preview 285,1 sn ("en gürültülü pencere, build'deki gibi") bekleniyordu; artık kural değişti, 174,61 ± 0,05 sn, F2'den 4 ölçü önce ve `prechorus_2` bekleniyor.
- `test_after_an_opening_the_sections_start_after_song`: `song_part` artık bir ad değil bölümün kendisi (`.name == "A1"`, başlangıcı 16 sn); `parts` da denetleniyor.
- `test_a_build_writes_its_sections_and_says_how_it_found_them` ve `test_a_build_of_a_song_that_never_changes_warns_and_forces_nothing`: yalnızca yeni denetimler eklendi (preview kaydı, `song.ini`, yedek kural uyarısı).
- `test_californication_structure_is_read_and_measured` (2026-11-15): proje sahibinin kriteri eklendi, preview insanınkinden en çok 1 ölçü uzakta (insan chart'ının o ölçüsü); `compare_structure` artık stem'ler yerine `analysis_signals(...)` alıyor.
- `test_californication_sections_beat_the_naive_boundaries`: yalnızca `compare_structure` çağrısı (`analysis_signals`), doğrulama aynı.
- Yeni (2026-11-15): `test_cli_build_asks_for_every_instrument_unless_told_otherwise` (`tests/test_pipeline.py`).
- Yeni: `tests/test_preview.py` (21 test: seçim, yedek kural, giriş, sığma, kısa şarkı, kesin kurallar, validator) ve `test_the_preview_line_says_how_the_preview_was_chosen` (2 test).

**Bellek (2026-11-15).** `-Full` iki kez `test_real_references_when_available` sırasında ya da hemen sonrasında Claude Code tarafından durduruldu. Ölçüm (bu test tek başına, yeni süreçte; özel bellek = commit edilen bellek):
- Önce: süreç import'larla 1,05 GB'ta başlıyor, test 3,21 GB'a çıkıyor (+2,16 GB). Tepe `estimate_tempo_map` sırasında: o anda Californication'ın 6 stereo stem'i (~0,8 GB), 4 stem'i yığınlayan `np.sum`'un sonucu ve tempo analizinin kendi geçici belleği (+0,96 GB) aynı anda duruyordu. Referans yükleme de `.sng`'nin 8 ses dosyasını önce hepsini çözüp sonra karıştırıyordu (+1,13 GB geçici).
- Değişiklikler (`evaluation/reference.py`, `evaluation/run.py`): referansın ses dosyaları tek tek çözülüp karışıma ekleniyor; stereo stem'lerden mono analiz sinyalleri ayrıştırmadan hemen sonra bir kez yapılıyor (`analysis_signals`) ve stem'ler tempo analizinden önce bırakılıyor; stem toplamları tek dizide, `np.sum`'la aynı toplamalar aynı sırada (Californication, Danza ve Toca'da bayt bayt aynı); `evaluate_folder` bir referansı bırakmadan sonrakini yüklemiyor. Demucs modeli önbellek varken hiç yüklenmiyor (yalnızca cihaz seçimi için torch import ediliyor, +0,15 GB, süreçten çıkarılamıyor). Test şarkı başına bölünmedi: tek referans var, gerek kalmadı.
- Sonra: tek başına 1,05 → 2,50 GB (+1,45 GB, önce +2,16). `-Full` içinde 1,35 → 2,53 GB. Değerlendirme raporu (JSON) değişiklikten önceki kodla bayt bayt aynı.
- **OpenBLAS (test ortamında uygulandı):** sürecin başlangıçtaki 1,05 GB'ının ~1 GB'ı OpenBLAS'ın iş parçacığı tamponları: numpy ve scipy ayrı OpenBLAS kopyası taşıyor, her biri 16 iş parçacığı için ~0,5 GB commit ediyor (`OPENBLAS_NUM_THREADS=1`: 71 MB, `=4`: 264 MB, varsayılan: 1036 MB). Bu sayfalar çoğunlukla dokunulmadığı için RAM'den çok commit payını tüketiyor; bu makinede commit payı dar (21 GB sınırın ~16 GB'ı `-Full` başlamadan dolu). `check.ps1` testleri artık 4 iş parçacığıyla çalıştırıyor, pencerenin önceki değerini sonunda geri koyuyor. Doğrulama: gitar (2 şarkı) ve bas (4 şarkı) hash testleri geçti; Şarkı Testi'nin tam build'i (gitar, bas, davul) varsayılan iş parçacığıyla yapılanla bayt bayt aynı (`analysis.json`'da yalnızca süreler farklı); aynı 86 test arka arkaya 4 / varsayılan / 4 / varsayılan: 59,8 / 60,9 / 58,1 / 59,8 sn, yani süre değişmiyor. `-Mid` geçti: 972 test, 506 sn, pytest tepe özel bellek 2,08 GB (gerçek Demucs testinde), en düşük boş commit 4,0 GB. 506 sn önceki `-Mid`'in (275 sn) iki katı, ama ortak 822 testin hepsi birlikte yavaşladı, OpenBLAS kullanmayan Demucs testleri dahil: makine yükü.
- **Üretim build'i için öneri (uygulanmadı):** `chartgen` komutu numpy'ı import etmeden önce `OPENBLAS_NUM_THREADS`'ı 4'e çekebilir (kullanıcı ortamda başka bir değer verdiyse ona dokunmadan). Build'in commit payı ~0,75 GB düşer; çıktı bu ölçümlerde aynı. Önce build süresi ve tepe bellek önce/sonra ölçülmeli, sonra karar.

**Kontroller:** gerçek şarkılar dışındaki bütün testler geçti (`-m "not slow and not real"`: 969 test, 290 sn); değişen değerlendirme koduyla ilgili 7 dosyanın `not real` testleri yeniden geçti (231 test). **`-Full` yine tamamlanmadı (2026-11-15):** 977 test bitti, hiçbiri başarısız olmadı (`-x` ilkinde dururdu), %94'te (Californication grubu, `test_the_configured_limit_costs_the_human_bass_chart_at_most_0_005`, ~830. sn) Claude Code arka plandaki işi "sistem belleği kritik, oturum boşta" diye durdurdu. O anda (son 5 sn'lik örnek) boş RAM 4,1 GB, boş commit 2,2 GB, pytest özel belleği 2,4 GB idi; izleyicinin 1,5 GB'lık kendi durdurma eşiğine hiç inilmedi. En düşük değerler referans testinde: boş RAM 3,57 GB, boş commit 1,97 GB (o sırada oturum boşta değildi, durdurulmadı). Koşunun en yüksek test tepesi Danza'nın gerçek build'i (2,71 GB); referans testi 2,53 GB. Sona kalan gerçek Demucs testleri (önceki koşularda 3,42 GB) çalışmadı. Californication preview testi ve kalan Californication testleri, gerçek Demucs testleri ve validator adımı D.2 koduyla henüz çalışmadı. Sonra proje sahibi `-Full`'u kendi penceresinde çalıştırdı: geçti (992 test, 745 sn; yukarıda "Şu anki adım").

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

**Bölümler, dk:sn** (`Songs`'daki kopyalar; Danza'nınki `Song` harf aldıktan sonra D.2'de yeniden kopyalandı):

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

- **Web editörü:** proje sahibinin ilk planındaki Phase 5: timeline, ses senkronu ve notaları elle düzeltme. Faz D kapanırken (2026-11-15) "ileride" listesine eklendi, başlanmadı.
- **Basta open note (`N 7`):** tekrar eden en alçak notalar için. Proje sahibinin önerisi, uygulanmadı.
- **Şarkı sözü (lyric olayları):** konuşma tanıma (Whisper gibi) ve sözlerin vokal notalarına hizalanması gerekir; yeni ve ağır bir bağımlılık. Proje sahibi 2026-11-11'de "yazma, ileride" dedi.
- **Davul star power fill'leri (`S 64`):** davulda star power'ın oyunda nasıl açıldığı doğrulanmadı (D.3). Deney `outputs\_experiments\d3_sp_deneyi\` altında, oyunda `SP Deneyi - Davul`. Proje sahibi 2026-11-15'te "şimdilik yazma, ileride test edeceğim" dedi.
- **Üretim build'inde `OPENBLAS_NUM_THREADS=4`:** testlerde uygulandı (2026-11-15), build için yalnızca öneri; önce süre ve tepe bellek ölçülmeli.
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
| D.1 | Bölüm tespiti, yapısal harfler, `Song` de harfli; Californication sınır F1 0,750 (eşik 0,70) | `838c88a` |
| D.2 | Preview: tekrar eden en gürültülü bölümün ikinci başlangıcından 4 ölçü önce; Californication insanınkinden 0,18 sn (kriter ≤ 1 ölçü); referans değerlendirmesinin belleği 3,21 → 2,50 GB | `f5e9551` |
| D.3 | Star power: dört enstrüman, 1 ölçü, ~25 sn arayla, dört seviyede aynı yerde; validator kuralları; davul fill'i yok, açılışı oyunda doğrulanmadı; Faz D kapandı | bu commit |

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
- **Referans sayısı:** 12 insan chart'ı (8 `train`, 4 `test`), `train`'in yarısı RHCP. Gitarın şerit ve sustain yumuşak hedefleri 3. adımdan beri `train`'den; diğerlerinin çoğu hâlâ Californication'dan, 4-5. adımlar onları `train`'den yeniden belirleyecek. Test yalnızca ölçülür.
- **Gitar şerit farkı (3. adımdan sonra açık, proje sahibinin kararı 2026-11-15):** `train` ortalamasında en kötü şerit farkı Expert 0,139 (hedef ≤ 0,10), Hard 0,157 (hedef ≤ 0,12); Expert'te yeşil 0,126 / 0,206, sarı 0,297 / 0,237. Ortak tek dağılımın tabanı 0,073. Bizde (0,3) ve (1,4) akor şekilleri yok (`SHAPES`, kesin kural), insanda %7. Medium (0,119) ve Easy (0,105) hedefte.
- **Hard akor oranı %42 / %58:** şerit düzeltmesi yalnızca freti değiştirdiği için bu oranı etkilemedi. Expert'te de oran insandan düşük (%50 / 59).
- **Distortion akor eşiği geçici önlem:** medyana bağlı eşik devreye girince terminalde ve `analysis.json`'da uyarıyor. Sert distortion'da akor doğruluğu ölçülmedi. `basic-pitch` eklenmedi: Python 3.11'e kadar destekliyor ve TensorFlow istiyor.
- **GPU determinizmi doğrulanmadı:** aynı stem'ler yalnızca bu makinenin CPU'sunda bit bit doğrulandı. Cihaz türleri önbellek paylaşmıyor.
- **Yön hedefi (açık):** gitar Expert'te insan şerit değiştirince `train` 0,316, test 0,274 (3. adımdaki hedef 0,35); Californication 0,604. Sınır pitch'in kendisi: distortion'lı gitarda kontur adımının işareti insanın yönüyle yalnızca ~%60 uyuşuyor, tekrar ile akor değişimini ayıran hiçbir özellik AUC 0,77'yi geçmedi.
- **Gitar sustain F1'i (açık):** `train` 0,382 (3. adımdaki hedef 0,45), test 0,406. Pay insana yakın (0,092 / 0,087) ama hangi notanın tutulduğu zayıf seçiliyor. Alt seviyelerde tek ayar: RHCP dışında fazla (Easy 0,067 / 0,018), RHCP'de az (Medium 0,039 / 0,094).
- **3. adımın şerit ayarları keys'i de etkiliyor:** keys gitarın `fret_weights.toml` ve `difficulty.toml`'unu kullanıyor; register, şerit önseli ve Medium/Easy `lane_map` değişiklikleri keys chart'larını da değiştirdi. Keys gerçek veriyle ölçülmediği için etkisi bilinmiyor. 3a (tekrar kuralı) ve 3d (sustain) yalnızca gitarda. **5a da keys'i etkiliyor** (proje sahibinin isteğiyle not, 2026-11-16): gitar Hard'ının `position_ratio`'su 0,67 → 0,80 keys Hard'ında da geçerli, yani keys Hard'ı Expert'in %80'ini tutuyor; keys gerçek veriyle ölçülmediği için bunun keys'e uyup uymadığı bilinmiyor (keys'in kendi dosyası yok).
- **Otomatik HOPO:** LastResort Expert %15.9 ve Hard %3.6, Şarkı Testi Expert %10.6, hedefler aşıldığı için uyarıyor. Davranış değiştirilmedi. `N 5` düzeltmesi gerçek şarkılarda hiç gerekmedi, yalnızca sentetik testte çalıştı.
- **Şerit hedefi başka şarkılarda sert olabilir:** build 3. adımdan beri `train` insanlarının ortalama paylarıyla karşılaştırıyor (±0,10). LastResort Easy'de kırmızı %65 (önce %75), oynarken tek düzelik hissedilmemişti.
- **Davul (4. adımdan sonra açık konular, proje sahibinin kararı 2026-11-16):** zil türleri hâlâ zayıf: `train`'de hi-hat/ride aynı şerit 0,691 (hedef 0,75), zil türü doğru 0,490 (0,60), mavi 0,257 (≤ 0,18; insan 0,122), yeşil 0,003 (≥ 0,05; insan 0,096), Expert gem farkı 0,146 (≤ 0,10); testte insan hi-hat'inin %63'ü mavi. Gevşek crash kuralı testte %15 isabetle düştü; eski sıkı kural duruyor. Tek başına kick Hard 0,132 / Medium 0,077 / Easy 0,218 (hedef 0,10 / 0,03 / 0,15). Tom'lar bulunmuyor (Holiday ve First Date'te insanın tom'ları bizde kick + zil). Snare'le aynı anda gelen ziller kaçıyor (insanın snare + hi-hat / snare + crash'i bizde yalnız snare).
- **5. adımdan sonra açık konular (2026-11-16):** gitar Hard F1'i yalnızca +0,015 arttı (proje sahibinin "belirgin" hedefi tutmadı): bizim Expert'ten kurulabilecek en iyi Hard 0,862, ama insanın hangi sekizlik ve on altılıkları attığını ölçüdeki yer, vuruş gücü ve cümle sonu ayırmıyor (on altılıkların %23'ü tutuluyor, güçten bağımsız); daha fazlası riff/tekrar yapısını bilmeyi gerektirir. Bas Hard'ın yoğunluğu insanın 0,92'si, Californication alt sınırı (0,77) yüzünden artırılamadı. Bas Medium'un en kötü şerit farkı 0,139 → 0,155 arttı. R1 test setinde 1981'in Easy konum F1'ini 0,617 → 0,573 düşürdü: o şarkının insan Easy'si kick'leri tutuyor; kural yalnızca 150 BPM üstünü ve kick + hi-hat'i kapsıyor, şarkı stiline bakmıyor.
- **Bölümler, hızlı şarkılar (2026-11-16):** 150 BPM üstünde ölçüler ikişer alınıyor (SPEC 46); Kids'in fazla bölünmesi düzeldi (31 → 8, insan 10) ama 1981'de insanın ~10 sn'lik bölümleri kaçıyor (8 → 6, insan 11; F1 0,526 → 0,353). Pencereyi saniyeyle ayarlamak ileride denenebilir. `train`'de 150 BPM üstünde tek şarkı var (First Date).
- **Star power, hızlı şarkılar (2026-11-16):** 10 ölçülük aralık 180 BPM üstünde dakikada 4,5-4,9 ifade veriyor (Zombiler, LastResort; yumuşak hedefin hemen üstü); 1981'in insanı daha seyrek koyuyor (7-8'e karşı 10-11). Dani ve Fat Lip'in insanı 5-6,5 ölçüde bir.
- **Davul tek referanstan:** sınıflandırıcının çoğu eşiği Californication'dan (rock). Tom ve crash doğrulanmadı (build bunu yazıyor). Danza ve Toca'da gem payı uyarıları, hedef paylar rock şarkılarından geldiği için (4. adımdan beri `train` ortalaması); oynarken sorun görülmedi.
- **Davul star power açılışı oyunda doğrulanmadı:** fill (`S 64`) yazılmıyor; deney hazır (D.3).
- **Star power'da seyrek ifade:** gitarda bazı ifadeler Easy'de tek nota tutuyor (Californication 1, LastResort 1, Şarkı Testi 1); uyarı veriyor.
- **Davul Expert'te flam:** 37-40 ms arayla iki konum kalabiliyor (C.1'in 35 ms birleştirme sınırının hemen üstü). Alt seviyelerde aralık kuralı bunları ayırıyor.
- **Tek ölçülük ölçü değişimleri bulunmuyor** (proje sahibinin kararı, 2026-11-15): Parallel Universe'ün insan chart'ındaki tek 6/4 ölçü (girişte, 4,03-6,97 sn) 6/4 olarak bulunmuyor; tempo haritası başa bir 2/4 ölçü koyup 4/4'e geçiyor, o ölçünün başını 994 ms ıskalıyor, hemen sonraki ölçüde faz geri geliyor (4/4 ölçülerin 141'inden 137'si tutuyor). Fat Lip'in insan chart'ında 4/8 ölçüler var; tempo doğru (98 BPM) ama ölçü çizgilerinin %49'u tutuyor.

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
