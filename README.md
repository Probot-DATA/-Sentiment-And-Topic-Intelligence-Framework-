# 📊 Sentiment & Topic Intelligence Framework (Power BI + ML + AI)

## 🔍 Overview
This project is a **configurable sentiment and topic analysis framework** designed to analyze user feedback (YouTube comments) across **dynamic, user-defined categories** such as games, products, companies, or A/B test phases.

The system automatically ingests comments from multiple URLs per category, performs **ML-based sentiment analysis**, **topic discovery**, and **AI-assisted topic interpretation**, and exposes insights through an **interactive Power BI dashboard** with automated refresh via a **personal gateway**.

---

## 🎯 Key Capabilities
- Supports **any number of categories**, each mapped to multiple YouTube URLs
- End-to-end pipeline from **raw comments → business insights**
- Fully **dynamic** (no hardcoded categories, topics, or visuals)

---

## 🧠 System Architecture (High Level)

1. **User Input**
   - User defines a category (e.g., *Brawl Stars*, *iPhone*, *Before Update / After Update*)
   - Multiple YouTube URLs can be mapped to each category
   - Sentinel value (`-1`) is used to terminate category or URL input

2. **Data Extraction**
   - YouTube comments are collected per URL
   - Metadata such as author, date, and URL are retained

3. **Sentiment Analysis**
   - Sentiment classification using **RoBERTa**
   - Outputs: `positive`, `neutral`, `negative`
   - A **custom rating (0–10)** is computed using:
     - Logits
     - Sigmoid scaling
     - Sarcasm/irony-aware adjustment (RoBERTa irony model)
   - Inspired by VADER-style composite scoring

4. **Topic Modeling**
   - Sentence embeddings generated using RoBERTa
   - **UMAP** for dimensionality reduction
   - **HDBSCAN** for density-based topic clustering
   - Topics and subtopics are created dynamically per category

5. **AI-Assisted Topic Interpretation**
   - LLMs are used to:
     - Generate **human-readable topic names**
     - Decide whether topics should be **generalized or preserved** for business clarity

6. **Data Storage**
   - Final structured table includes:
     - Category
     - Topic
     - Subtopic
     - Sentiment
     - Rating
     - Date
     - URL
     - Author
     - Additional metadata

7. **Visualization & Reporting**
   - Interactive Power BI dashboards:
     - Sentiment distribution
     - Category comparisons
     - Rating trends
     - Topic-level insights
   - Connected to **Power BI Service via Personal Gateway**
   - Supports **scheduled refresh** from local data sources

---

## 📊 Dashboard Design
The Power BI report is structured into multiple analytical layers:

- **Page 1 – Overview**
  - Overall sentiment distribution
  - Review volume
  - Rating summaries
  - Topic-level aggregation

- **Page 2 – Deep Dive**
  - Topic × sentiment breakdown
  - Day-wise sentiment trends
  - Key influencers for negative sentiment

- **Page 3 – Category Comparison**
  - Sentiment comparison across categories
  - Rating trends by category
  - Synchronized slicers for consistent analysis

---

## 🔌 Data Refresh & Gateway
- Uses **On-premises Data Gateway (Personal Mode)**
- Enables scheduled refresh from locally generated datasets
- Gateway is mapped at the **dataset level** in Power BI Service
- Ensures dashboards stay up-to-date without manual intervention

---

## 🛠 Tech Stack
**Languages & Tools**
- Python
- Power BI (Desktop & Service)

**Machine Learning / NLP**
- RoBERTa (Sentiment & Irony Detection)
- Sentence Transformers
- UMAP
- HDBSCAN

**AI / LLM**
- Topic naming & generalization prompts

**Data Handling**
- Pandas

---

## 📌 Design Decisions
- Topic-level slicers were intentionally avoided on comparison pages to preserve **category-level comparability**
- Topic insights are shown visually rather than filtered to prevent analytical distortion
- Scope was controlled to prioritize **clarity and storytelling over feature overload**

---

## ⚠️ Limitations
- The pipeline is **not GPU-optimized** and currently runs on CPU-based inference, which results in longer execution times for large datasets.
- The framework relies on **offline batch processing** of comments rather than real-time streaming ingestion.
- Topic modeling is performed **independently per category**, and cross-category (global) topic alignment is not implemented.
- UMAP and HDBSCAN hyperparameters are **statically configured** and were empirically optimized for datasets in the range of approximately **12k–16k comments**.
- AI-assisted topic naming and generalization rely on **free-tier LLMs**, which may limit output quality compared to higher-capability commercial models.
- Review extraction is currently **limited to YouTube**, as scraping support for other platforms (e.g., Reddit, Instagram, Twitter) was restricted due to API or access constraints.
- Although a RoBERTa-based sentiment model is used, it may struggle with **domain-specific or implicit sentiment**, where meaning depends on contextual or community knowledge (e.g., phrases like “pay-to-win” in gaming contexts may be classified as neutral despite carrying negative sentiment).

---

## 🧑‍💻 Author
**Prabhat Mukku**  
Data Science & Analytics  
Power BI | NLP | ML | AI-assisted analytics
