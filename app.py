import streamlit as st
import requests
import pandas as pd
import datetime
import re
import time
import concurrent.futures
import os

# 🔑 API Key Hardcoded untuk Testing
API_KEY = os.getenv('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
LOGO_PATH = os.getenv('LOGO_PATH')

# 🔎 Daftar kata kunci positif dan negatif
POSITIVE_KEYWORDS = ["ekspansi", "laba meningkat", "penghargaan", "inovasi", "kerja sama", "investasi", "pertumbuhan", "sukses"]
NEGATIVE_KEYWORDS = ["masalah", "penipuan", "gagal bayar", "denda", "kredit macet", "skandal", "investigasi", "kebangkrutan"]

# 🗓️ Fungsi untuk mengekstrak tanggal terbit dari Google API
def extract_publish_date(item):
    pub_date = (
        item.get("pagemap", {}).get("metatags", [{}])[0].get("datePublished") or
        item.get("pagemap", {}).get("newsarticle", [{}])[0].get("datepublished") or
        item.get("pagemap", {}).get("metatags", [{}])[0].get("date") or
        None
    )
    if pub_date:
        try:
            return datetime.datetime.fromisoformat(pub_date)
        except ValueError:
            pass

    snippet = item.get("snippet", "")
    date_match = re.search(r"\b(\d{1,2} \w+ \d{4})\b", snippet)
    if date_match:
        try:
            return datetime.datetime.strptime(date_match.group(1), "%d %B %Y")
        except ValueError:
            pass
    return None

# 🔍 Fungsi untuk mencari berita di Google Search API
def search_google(base_query, keywords, max_results=300):
    results = []
    results_per_page = 10  # Google API hanya mengembalikan max 10 per request

    for keyword in keywords:
        total_fetched = 0
        while total_fetched < max_results:
            start_index = total_fetched + 1  # Start pagination (1, 11, 21, ...)
            query = f"{base_query} {keyword} -site:mizuho-ls.co.id -site:digital-bucket.prod.bfi.co.id -site:buanafinance.co.id"
            url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={API_KEY}&cx={SEARCH_ENGINE_ID}&start={start_index}"

            response = requests.get(url)
            data = response.json()
            
            if "items" not in data:
                break  # Jika tidak ada data, berhenti

            for item in data["items"]:
                title = item.get("title", "No title available")
                link = item.get("link", "#")
                snippet = item.get("snippet", "No description available")
                pub_date = extract_publish_date(item) or "Tanggal Tidak Diketahui"

                # 🎯 **Menentukan sentimen dengan prioritas negatif**
                sentiment = "Neutral"

                # 🔴 **Jika ada kata negatif, langsung dianggap negatif**
                if any(neg in title.lower() or neg in snippet.lower() for neg in NEGATIVE_KEYWORDS):
                    sentiment = "Negative"
                # 🟢 **Jika ada kata positif dan tidak ada kata negatif, dianggap positif**
                elif any(pos in title.lower() or pos in snippet.lower() for pos in POSITIVE_KEYWORDS):
                    sentiment = "Positive"

                results.append({
                    "Title": title, 
                    "Link": link, 
                    "Snippet": snippet,  
                    "Sentiment": sentiment, 
                    "Published Date": pub_date
                })

            total_fetched += results_per_page
            time.sleep(1)  # Tambahkan delay untuk menghindari rate limit API

    return results


# 🎨 Streamlit UI
st.set_page_config(layout="wide", page_title="Mizuho Leasing Social Media Insight", page_icon="🔎")

# 🏠 Sidebar Branding
with st.sidebar:
    try:
        st.image(LOGO_PATH, width=300)
    except:
        st.warning("Logo tidak ditemukan, pastikan path benar!")

    st.markdown("### **Filter Berita Berdasarkan Sentimen**")
    sentiment_filter = st.radio("Pilih Sentimen:", ["All", "Positive", "Negative"])

# ✅ **Gunakan Session State agar tidak tarik API berulang**
st.title("📊 Mizuho Leasing Indonesia - Social Media Insight")
st.markdown("🔍 **Analisis berita dari Google Search API berdasarkan sentimen positif dan negatif**")

if "news_data" not in st.session_state:
    with st.spinner("Mengambil 300 berita terbaru..."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_positive = executor.submit(search_google, "Mizuho Leasing Indonesia", POSITIVE_KEYWORDS, 100)
            future_negative = executor.submit(search_google, "Mizuho Leasing Indonesia", NEGATIVE_KEYWORDS, 100)

            positive_news = future_positive.result()
            negative_news = future_negative.result()

        st.session_state.news_data = positive_news + negative_news  # Simpan hasil API di session state

# Gunakan data yang sudah diambil sebelumnya
news_data = st.session_state.news_data

if not news_data:
    st.warning("Tidak ada berita ditemukan.")
else:
    df = pd.DataFrame(news_data)
    df = df[df["Published Date"] != "Tanggal Tidak Diketahui"]
    df["Published Date"] = pd.to_datetime(df["Published Date"], errors="coerce")
    df = df.sort_values(by="Published Date", ascending=False)

    # 🎯 **Filter berita berdasarkan sentimen TANPA tarik API ulang**
    if sentiment_filter != "All":
        df = df[df["Sentiment"] == sentiment_filter]

    # Fungsi styling tabel (warna berdasarkan sentimen)
    def highlight_sentiment(val):
        color = "green" if val == "Positive" else "red" if val == "Negative" else "grey"
        return f"background-color: {color}; color: white"

    # **Tampilkan tabel dengan warna sentimen**
    st.subheader("📌 Hasil Pencarian Berita")
    st.dataframe(df.style.applymap(highlight_sentiment, subset=["Sentiment"]))

    # **Tampilkan daftar berita sebagai list dengan link**
    for _, row in df.iterrows():
        st.markdown(f"### [{row['Title']}]({row['Link']})")
        st.write(f"📰 {row['Snippet']}")
        st.write(f"📅 **Tanggal Terbit:** {row['Published Date'].strftime('%d %B %Y')}")
        st.write(f"🟢 **Sentiment:** {row['Sentiment']}" if row['Sentiment'] == "Positive" else f"🔴 **Sentiment:** {row['Sentiment']}")
        st.write("---")

st.markdown("🚀 **Dibangun oleh AI Anytime** | 🔗 [GitHub](https://github.com/AIAnytime)")
