# Auto Sentiment Analyser

An end-to-end sentiment analysis and topic discovery project for gaming-related user feedback collected from multiple platforms such as YouTube, Reddit, Google Play, Steam, and Amazon.

This project extracts comments/reviews, cleans and standardizes text, performs sentiment classification, discovers local and global topics, generalizes topic names with an LLM workflow, and prepares the final dataset for dashboarding in Power BI.

---

## Project Overview

The goal of this project is to turn raw user feedback into structured insights by answering questions like:

- What are users feeling about each game/product?
- Which issues or praise themes appear most often?
- What topics are specific to a single category?
- What broader topics appear across all categories?
- How can these insights be visualized for decision-making?

The project combines:

- Multi-source review extraction
- Text preprocessing and cleaning
- Sentiment scoring
- Topic modeling
- Topic label merging and generalization
- Power BI dashboarding

---

## Features

- Collects data from multiple review/comment sources
- Cleans and normalizes raw text
- Classifies sentiment for each review
- Generates local topics within each category
- Generates global topics across the full dataset
- Merges raw topic IDs with readable topic names
- Creates generalized topic labels for cleaner reporting
- Exports final structured output to Excel
- Supports Power BI dashboards for business analysis

---

## Workflow

### 1. Data Extraction
The notebook collects comments/reviews from sources such as:

- YouTube
- Reddit
- Google Play
- Steam
- Amazon

The extracted records include fields such as:

- `url`
- `author`
- `Text`
- `date`
- `source`
- `category`
- `parsed_date`
- `domain`

### 2. Data Cleaning
Raw text is cleaned by:

- converting to lowercase
- removing URLs
- removing HTML entities
- tokenizing text
- dropping empty or invalid rows
- removing duplicates

### 3. Sentiment Analysis
The pipeline performs sentiment classification and assigns values such as:

- sentiment label
- rating/score

This produces structured sentiment outputs for every text entry.

### 4. Topic Modeling
The project builds topic clusters using transformer embeddings and clustering methods.

It includes:

- local topics per category
- global topics across the entire dataset
- topic quality and confidence metrics
- topic diversity calculations

### 5. Topic Name Generalization
LLM-based processing is used to convert raw topic names into cleaner, generalized business-friendly labels.

### 6. Final Export
The final enriched dataset is exported to Excel and used in Power BI for visualization.

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

## 🧑‍💻 Author
**Prabhat Mukku**  
Data Science & Analytics  
Power BI | NLP | ML | AI-assisted analytics
