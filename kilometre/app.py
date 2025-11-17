import streamlit as st
import zipfile
import tempfile
import os
import time
import pandas as pd
from PIL import Image
from google import genai
from google.api_core.exceptions import ResourceExhausted
from datetime import datetime
import io

# ======================================================
# Streamlit Arayüz Başlığı
# ======================================================
st.title("Kilometre Okuma Uygulaması")
st.write("Araç fotoğraflarından kilometre değerlerini otomatik olarak okur.")

# ======================================================
# 1. API KEY GİRİŞİ
# ======================================================
api_key = st.text_input("🔑 Gemini API Keyinizi Girin:", type="password")
if not api_key:
    st.warning("Lütfen API Key giriniz.")
    st.stop()

# Gemini Client oluşturma
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"API Key geçersiz! Hata: {e}")
    st.stop()

# ======================================================
# 2. ZIP DOSYASINI ALMA
# ======================================================
zip_file = st.file_uploader("📁 Fotoğraflarınızı ZIP olarak yükleyin:", type=["zip"])
if not zip_file:
    st.info("Lütfen ZIP dosyası yükleyin.")
    st.stop()

# ======================================================
# 3. ZIP DOSYASINI GEÇİCİ KLASÖRE AÇ
# ======================================================
temp_dir = tempfile.mkdtemp()
with zipfile.ZipFile(zip_file, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

# Fotoğraf dosyalarını topla
dosyalar = [
    f for f in os.listdir(temp_dir)
    if f.lower().endswith(('.png', '.jpg', '.jpeg'))
]
dosyalar.sort()

st.success(f"{len(dosyalar)} adet görsel bulundu. İşlem başlatılabilir.")

# ======================================================
# 4. İŞLEME BUTONU
# ======================================================
if st.button("🚀 Kilometre Okumayı Başlat"):
    st.write("İşleniyor...")

    PROMPT = "Aracın kilometre bilgisi nedir? Sadece kilometre bilgisini yaz."
    BEKLEME = 3
    MAX_SIZE = (384, 384)

    sonuçlar = []

    progress = st.progress(0)
    total = len(dosyalar)

    # Fotoğrafları yan yana göstermek için sütunlar oluştur
    for idx, dosya in enumerate(dosyalar):
        dosya_yolu = os.path.join(temp_dir, dosya)
        
        # Her 3 fotoğrafı yan yana göster
        if idx % 3 == 0:
            cols = st.columns(3)
        
        with cols[idx % 3]:
            st.write(f"**{dosya}**")
            image = Image.open(dosya_yolu)
            st.image(image, use_container_width=True)

            # Görseli küçült
            if image.width > MAX_SIZE[0] or image.height > MAX_SIZE[1]:
                image.thumbnail(MAX_SIZE)

            # Gemini API çağrısı
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[PROMPT, image]
                )

                kilometre = response.text.strip()
                st.write(f"🔢 **KM:** {kilometre}")

                sonuçlar.append({
                    "dosya_adi": dosya,
                    "km": kilometre
                })

            except ResourceExhausted:
                st.error("❌ Kota aşıldı! Daha sonra tekrar deneyin.")
                break
            except Exception as e:
                st.error(f"Hata: {e}")
                sonuçlar.append({"dosya_adi": dosya, "km": "Hata"})
        
        progress.progress((idx + 1) / total)
        time.sleep(BEKLEME)

    # ======================================================
    # 5. SONUÇLARI TABLO VE CSV OLARAK SUN
    # ======================================================
    if sonuçlar:
        df = pd.DataFrame(sonuçlar)

        # km değerlerini analiz et
        df_km = df["km"].value_counts()
        df_km = df_km.reset_index()
        df_km.columns = ["km", "count"]

        # km yazısını temizle ve sayıya çevir
        df_km["km"] = df_km["km"].str.replace(" km", "").str.replace("km", "")
        df_km["km"] = df_km["km"].str.extract(r"(\d+)")
        df_km = df_km.dropna()  # Boş değerleri kaldır
        df_km["km"] = df_km["km"].astype(int)

        # Sırala
        df_km = df_km.sort_values("km").reset_index(drop=True)

        # Giriş-Çıkış eşleştirme
        pairs = []
        i = 0
        while i < len(df_km) - 1:
            km1 = df_km.loc[i, "km"]
            km2 = df_km.loc[i+1, "km"]

            if km1 == km2 or abs(km2 - km1) == 1:
                if i+1 < len(df_km):
                    df_km.loc[i+1, "km"] -= 1
                i += 1
            else:
                pairs.append((km1, km2))
                i += 1

        if pairs:
            result = pd.DataFrame(pairs, columns=["Giriş", "Çıkış"])
            result["Fark"] = result["Çıkış"] - result["Giriş"]

            st.subheader("📊 Giriş – Çıkış – Fark Sonuçları")
            st.dataframe(result, use_container_width=True)

            # ======================================================
            # 6. EXCEL OLARAK İNDİRME
            # ======================================================
            today = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
            excel_name = f"{today}-Kilometre.xlsx"

            buffer = io.BytesIO()

            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                result.to_excel(writer, sheet_name="Sonuçlar", index=False)
                # df.to_excel(writer, sheet_name="Ham Veri", index=False)
            
            buffer.seek(0)

            st.download_button(
                label="📥 Excel Dosyasını İndir",
                data=buffer,
                file_name=excel_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.success("✅ İşlem tamamlandı!")
        else:

            st.warning("Eşleştirme yapılabilecek yeterli veri bulunamadı.")
