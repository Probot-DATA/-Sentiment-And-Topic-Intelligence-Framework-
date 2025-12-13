# 🎮 Case Study: Sentiment & Topic Analysis of Mobile Games (YouTube Reviews)

## 📌 Overview
This case study applies the **Sentiment & Topic Intelligence Framework** to analyze player feedback for multiple mobile games using **YouTube comments**. The goal is to understand **player sentiment, dominant discussion topics, rating behavior, and category-level differences** through an interactive Power BI dashboard.

The analysis focuses on three Supercell games and demonstrates how unstructured player feedback can be converted into **actionable product insights**.

---

## 🗂️ Categories Analyzed
Each game is treated as a separate analytical category:

- **Brawl Stars**
- **Clash of Clans**
- **Clash Royale**

Each category includes comments extracted from multiple YouTube videos such as update reviews, gameplay discussions, and community feedback content.

---

## 📊 Dataset Summary
- **Total reviews analyzed:** ~42,000 comments
- **Sentiment split (overall):**
  - Negative: **~42.6%**
  - Neutral: **~28.5%**
  - Positive: **~28.9%**
- **Date range:** 20-Nov-2025 to 04-Dec-2025

---

## 🔍 Key Analytical Dimensions

### 1️⃣ Sentiment Analysis
- Each comment is classified as **positive**, **neutral**, or **negative** using a RoBERTa-based sentiment model.
- Sentiment distribution is analyzed:
  - Overall
  - By topic
  - By day
  - By category (game)

---

### 2️⃣ Rating Analysis
- A composite **rating score (0–10)** is derived for each comment using model logits, sigmoid scaling, and sarcasm-aware adjustment.
- Ratings are analyzed:
  - Across predefined rating bins (0–2, 2–4, …, 8–10)
  - As daily averages
  - By category over time

---

### 3️⃣ Topic Modeling
- Discussion topics are identified using **UMAP + HDBSCAN** clustering on sentence embeddings.
- Topics are generated **independently per category** and include themes such as:
  - Player feedback and suggestions
  - Update and balance changes
  - Community and engagement issues
  - Progression and monetization concerns
- Topics are further analyzed by sentiment to identify **pain points**.

---

## 📈 Dashboard Structure

### **Page 1 – Overview**
Provides a high-level view of player feedback:
- Overall sentiment percentages
- Total review volume
- Topic-wise review distribution
- Rating distribution and daily rating trends

---

### **Page 2 – Deep Dive**
Focuses on **drivers of sentiment**:
- Topic × sentiment breakdown
- Day-wise sentiment trends
- Key Influencers analysis identifying factors that increase the likelihood of negative sentiment  
  (e.g., payment issues, player retention concerns, audio/visual feedback)

---

### **Page 3 – Category Comparison**
Enables direct comparison across games:
- Sentiment distribution by category
- Average rating trends by game
- Relative review volume per category
- Synchronized slicers to maintain consistent analytical context

---

## 🧠 Key Observations
> *Insights vary dynamically based on selected categories and date ranges.*

- **Clash Royale** shows the highest volume of negative sentiment, with monetization and progression-related topics contributing significantly.
- **Brawl Stars** exhibits comparatively more stable sentiment and ratings.
- **Clash of Clans** maintains steady ratings but shows lower engagement volume during the observed period.
- Certain domain-specific phrases (e.g., *“pay-to-win”*) carry implicit negative sentiment that may not always be explicitly expressed.

---

## 🔌 Data Refresh & Deployment
- The dashboard is connected to **Power BI Service** using an **On-premises Data Gateway (Personal Mode)**.
- Data is refreshed on a scheduled basis from locally generated datasets.
- Gateway configuration is performed at the **dataset level**, enabling automated updates without manual intervention.

---

## ⚠️ Limitations
- Analysis is limited to **YouTube comments**, which may not fully represent sentiment from other platforms.
- Topic modeling is performed **per category**, without global topic alignment across games.
- Sentiment models may struggle with **implicit or domain-specific sentiment**, particularly in gaming contexts.
- Execution time is higher due to **CPU-only inference** and lack of GPU optimization.

---

## 🎯 Why This Case Study Matters
This case study demonstrates how large volumes of unstructured player feedback can be transformed into:
- Quantifiable sentiment metrics
- Topic-level product insights
- Category-wise performance comparisons

The same analytical approach can be extended to:
- Product reviews
- Feature A/B testing
- Community health monitoring
- Brand perception analysis

---

## 🔗 Related
- **Framework:** Sentiment & Topic Intelligence Framework
- **Visualization:** Power BI
- **Data Source:** YouTube Comments
