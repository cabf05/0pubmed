import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import datetime

st.set_page_config(page_title="PubMed Relevance Ranker", layout="wide")

st.title("🔍 PubMed Relevance Ranker")

st.markdown("This tool fetches articles from PubMed and ranks them based on their **potential relevance**, using only metadata from the PubMed XML.")

# -------------------- Inputs --------------------
st.header("Step 1: Customize the Search")

default_query = '("Endocrinology" OR "Diabetes") AND 2024/10/01:2025/06/28[Date - Publication]'
query = st.text_area("PubMed Search Query", value=default_query, height=100)

default_journals = "\n".join([
    "N Engl J Med", "JAMA", "BMJ", "Lancet", "Nature", "Science", "Cell"
])
journal_input = st.text_area("High-Impact Journals (one per line)", value=default_journals, height=150)
journals = [j.strip().lower() for j in journal_input.strip().split("\n") if j.strip()]

default_institutions = "\n".join([
    "Harvard", "Oxford", "Mayo Clinic", "NIH", "Stanford",
    "UCSF", "Yale", "Cambridge", "Karolinska", "Johns Hopkins"
])
inst_input = st.text_area("Renowned Institutions (one per line)", value=default_institutions, height=150)
institutions = [i.strip().lower() for i in inst_input.strip().split("\n") if i.strip()]

hot_keywords = ["glp-1", "semaglutide", "tirzepatide", "ai", "machine learning", "telemedicine"]

if st.button("🔎 Run PubMed Search"):
    with st.spinner("Fetching articles..."):

        # Step 1: Use esearch to get PMIDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "retmax": "250",
            "retmode": "json",
            "term": query
        }
        r = requests.get(search_url, params=search_params)
        id_list = r.json()["esearchresult"].get("idlist", [])

        def fetch_article(pmid):
            efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml"
            }
            try:
                response = requests.get(efetch_url, params=params, timeout=10)
                if response.status_code != 200 or not response.content:
                    return None
                root = ET.fromstring(response.content)
                article = root.find(".//PubmedArticle")
                return article
            except Exception:
                return None

        def score_article(article):
            score = 0
            reasons = []

            journal = article.findtext(".//Journal/Title", "").lower()
            if any(j in journal for j in journals):
                score += 2
                reasons.append("High-impact journal (+2)")

            pub_types = [pt.text.lower() for pt in article.findall(".//PublicationType")]
            valued_types = ["randomized controlled trial", "systematic review", "meta-analysis", "guideline", "practice guideline"]
            if any(pt in valued_types for pt in pub_types):
                score += 2
                reasons.append("Valued publication type (+2)")

            authors = article.findall(".//Author")
            if len(authors) >= 5:
                score += 1
                reasons.append("Multiple authors (+1)")

            affiliations = [aff.text.lower() for aff in article.findall(".//AffiliationInfo/Affiliation") if aff is not None]
            if any(inst in aff for aff in affiliations for inst in institutions):
                score += 1
                reasons.append("Prestigious institution (+1)")

            title = article.findtext(".//ArticleTitle", "").lower()
            if any(kw in title for kw in hot_keywords):
                score += 2
                reasons.append("Hot keyword in title (+2)")

            if article.find(".//GrantList") is not None:
                score += 2
                reasons.append("Has research funding (+2)")

            return score, "; ".join(reasons)

        records = []
        for pmid in id_list:
            article = fetch_article(pmid)
            if article is None:
                continue
            try:
                title = article.findtext(".//ArticleTitle", "")
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                journal = article.findtext(".//Journal/Title", "")
                date = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate") or "N/A"
                score, reason = score_article(article)
                records.append({
                    "Title": title,
                    "Link": link,
                    "Journal": journal,
                    "Date": date,
                    "Score": score,
                    "Why": reason
                })
            except Exception:
                continue

        df = pd.DataFrame(records).sort_values("Score", ascending=False)

        st.success(f"Found {len(df)} articles.")
        st.dataframe(df[["Title", "Journal", "Date", "Score", "Why"]], use_container_width=True)

        csv = df.to_csv(index=False)
        st.download_button("⬇️ Download CSV", data=csv, file_name="ranked_pubmed_results.csv", mime="text/csv")
