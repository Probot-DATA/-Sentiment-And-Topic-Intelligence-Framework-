import argparse
import math
import re
import sys
from pathlib import Path


def check_dependencies():
    missing = []
    for pkg in [
        "pandas",
        "numpy",
        "nltk",
        "torch",
        "transformers",
        "sentence_transformers",
        "umap",
        "hdbscan",
        "sklearn",
    ]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing required Python packages: {', '.join(missing)}", file=sys.stderr)
        print("Tip: Run using the project's ML environment, e.g.: C:\\ai_env\\Scripts\\python.exe", file=sys.stderr)
        sys.exit(1)


check_dependencies()

import hdbscan
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
import umap
from nltk.tokenize import word_tokenize
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline


# ----------------------------
# DATA CLEANING (Notebook Cell 5)
# ----------------------------
def clean(row):
    row = str(row).lower()
    row = re.sub(r"https\S+|www.\S+", "", row)
    row = re.sub(r"&lt;|&gt;|&amp;", " ", row)
    row = row.strip()

    words = word_tokenize(row)
    if len(words) == 0:  # less aggressive
        return None
    return row


# ----------------------------
# SENTIMENT & IRONY SCORING (Notebook Cell 9, Ollama fallback excluded)
# ----------------------------
def get_sentiment_and_score(texts, sources, categories, encoder, sentiment_model, irony_model, device, batch=8):
    results = []

    for i in range(0, len(texts), batch):
        batch_texts = list(texts[i : i + batch])
        batch_sources = list(sources[i : i + batch])
        batch_categories = list(categories[i : i + batch])

        encoded = encoder(
            batch_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        )

        encoded = {k: v.to(device) for k, v in encoded.items()}

        with torch.inference_mode():
            outputs = sentiment_model(**encoded)
            logits = outputs.logits
            probs = F.softmax(logits, dim=1)

        pred_ids = torch.argmax(logits, dim=1)

        id2label = {0: "negative", 1: "neutral", 2: "positive"}
        weights = torch.tensor([2.0, 3.0, 8.0], device=device)

        ratings = (probs * weights).sum(dim=1)

        # sarcasm batch
        irony_outputs = irony_model(batch_texts, truncation=True, max_length=256)
        sarcasm_scores = torch.tensor(
            [o["score"] if o["label"] == "irony" else 0.0 for o in irony_outputs],
            device=device,
        )

        ratings = ratings - 0.75 * sarcasm_scores
        ratings = torch.clamp(ratings, 0, 10)

        for txt, pid, rating, src, cat, sarcasm in zip(
            batch_texts, pred_ids, ratings, batch_sources, batch_categories, sarcasm_scores
        ):
            sentiment = id2label[int(pid.item())]
            final_rating = float(rating.item())

            # Note: Ollama LLM fallback for neutral / high-sarcasm rows is intentionally excluded.

            # -------- platform weighting --------
            platform_weight = {
                "youtube": 1,
                "reddit": 1,
                "steam": 1,
                "googleplay": 1,
                "amazon": 1,
            }

            final_rating = final_rating * platform_weight.get(src, 1.0)
            final_rating = max(0, min(10, final_rating))

            results.append(
                {
                    "Text": txt,
                    "Sentiment": sentiment,
                    "Rating": final_rating,
                }
            )

    return results


# ----------------------------
# TOPIC QUALITY HELPERS (Notebook Cell 15)
# ----------------------------
def topic_diversity(topic_keywords, top_k=10):
    words = []
    for topic_id, kw in topic_keywords.items():
        if topic_id == -1 or kw == "Misc / Noise":
            continue
        parts = [w.strip() for w in kw.split(",")[:top_k] if w.strip()]
        words.extend(parts)

    if len(words) == 0:
        return np.nan

    return len(set(words)) / len(words)


def safe_topic_quality(cluster_labels, probabilities, topic_keywords):
    labels = np.asarray(cluster_labels)
    mask = labels != -1  # ignore noise

    if mask.sum() == 0:
        return np.nan, np.nan, np.nan

    if probabilities is not None and len(probabilities) == len(labels):
        avg_confidence = float(np.mean(probabilities[mask]))
    else:
        avg_confidence = np.nan

    diversity = topic_diversity(topic_keywords)

    if np.isnan(avg_confidence) and np.isnan(diversity):
        quality = np.nan
    elif np.isnan(avg_confidence):
        quality = diversity
    elif np.isnan(diversity):
        quality = avg_confidence
    else:
        quality = 0.5 * avg_confidence + 0.5 * diversity

    return (
        float(quality),
        float(avg_confidence) if not np.isnan(avg_confidence) else np.nan,
        float(diversity) if not np.isnan(diversity) else np.nan,
    )


# ----------------------------
# TOPIC EXTRACTION FUNCTION (Notebook Cell 15)
# ----------------------------
def build_topics(df, transformer, device, text_col="text", topic_col="Topic", keyword_col="Topic_Keywords"):
    n_rows = len(df)
    out = df.copy()
    out[text_col] = out[text_col].fillna("").astype(str)

    texts = out[text_col].tolist()
    n = len(texts)

    if n == 0:
        out[topic_col] = []
        out[keyword_col] = []
        out["Topic_Quality_Score"] = np.nan
        out["Cluster_Confidence"] = np.nan
        out["Topic_Diversity"] = np.nan
        return out, np.nan

    embeddings = transformer.encode(
        texts,
        batch_size=64 if device == "cuda" else 32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    if n < 5:
        out[topic_col] = 0
        out[keyword_col] = "Misc / Noise"
        out["Cluster_Confidence"] = np.nan
        out["Topic_Diversity"] = np.nan
        return out, np.nan

    n_neighbors = int(min(50, max(12, round(math.sqrt(n_rows) * 1.2))))
    # Safeguard for small datasets where n_rows <= n_neighbors
    n_neighbors = max(2, min(n_neighbors, n - 1))
    n_components = 10 if n_rows >= 1200 else 8
    n_components = max(2, min(7, n - 1))

    # For small n (< 10), spectral layout fails in scipy eigsh (k >= N); use 'random' init
    init_mode = "random" if n < 10 else "spectral"
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        metric="cosine",
        init=init_mode,
        random_state=42,
    )
    try:
        umap_embeddings = umap_model.fit_transform(embeddings)
    except Exception:
        umap_model = umap.UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            metric="cosine",
            init="random",
            random_state=42,
        )
        umap_embeddings = umap_model.fit_transform(embeddings)

    min_cluster_size = int(min(30, max(6, round(n_rows * 0.015))))
    min_samples = int(min(6, max(2, round(min_cluster_size * 0.35))))

    hdb_model = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method="eom",
    )

    cluster_labels = hdb_model.fit_predict(umap_embeddings)

    # Build keyword summary per topic
    temp = pd.DataFrame({"text": out[text_col].values, "topic": cluster_labels})

    topic_text_map = {}
    for topic_id in temp["topic"].unique():
        joined_text = " ".join(temp[temp["topic"] == topic_id]["text"].tolist())
        topic_text_map[topic_id] = joined_text

    topic_df = pd.DataFrame(
        {
            "topic": list(topic_text_map.keys()),
            "text": list(topic_text_map.values()),
        }
    )

    vectorizer = TfidfVectorizer(stop_words="english")

    if len(topic_df) > 0 and topic_df["text"].str.strip().any():
        try:
            matrix_tfidf = vectorizer.fit_transform(topic_df["text"]).toarray()
            feature_names = vectorizer.get_feature_names_out()

            topic_keywords = {}
            for topic_id, row in zip(topic_df["topic"], matrix_tfidf):
                if topic_id == -1:
                    topic_keywords[topic_id] = "Misc / Noise"
                    continue

                top_idx = np.argsort(row)[-20:][::-1]
                top_words = [feature_names[i] for i in top_idx if row[i] > 0]
                if len(top_words) == 0:
                    topic_keywords[topic_id] = "Misc / Noise"
                else:
                    topic_keywords[topic_id] = ", ".join(top_words[:20])
        except ValueError:
            topic_keywords = {t: "Misc / Noise" for t in temp["topic"].unique()}
    else:
        topic_keywords = {t: "Misc / Noise" for t in temp["topic"].unique()}

    # Quality metric
    topic_quality, avg_confidence, diversity = safe_topic_quality(
        cluster_labels,
        getattr(hdb_model, "probabilities_", None),
        topic_keywords,
    )

    out[topic_col] = cluster_labels
    out[keyword_col] = out[topic_col].map(topic_keywords).fillna("Misc / Noise")

    probs = getattr(hdb_model, "probabilities_", None)
    if probs is not None and len(probs) == len(out):
        out["Cluster_Confidence"] = probs
    else:
        out["Cluster_Confidence"] = np.nan

    out["Topic_Diversity"] = diversity

    return out, topic_quality


# ----------------------------
# BUILD LOCAL + GLOBAL TOPICS (Notebook Cell 15)
# ----------------------------
def build_complete_dataset(new_data, transformer, device):
    local_parts = []
    validation_rows = []

    # Local topics per category
    for category in new_data["category"].dropna().unique():
        subdf = new_data[new_data["category"] == category].copy()

        local_df, local_score = build_topics(
            subdf,
            transformer=transformer,
            device=device,
            text_col="text",
            topic_col="Local_Topic",
            keyword_col="Local_Topic_Keywords",
        )

        local_df["Local_Topic_Quality"] = local_score
        local_parts.append(local_df)

        validation_rows.append(
            {
                "Scope": "Local",
                "Category": category,
                "Topic_Quality_Score": local_score,
                "Rows": len(local_df),
                "Num_Topics": local_df["Local_Topic"].nunique(),
            }
        )

    local_complete = pd.concat(local_parts, ignore_index=True) if local_parts else pd.DataFrame()

    # Global topics across all data
    global_complete, global_score = build_topics(
        new_data.copy(),
        transformer=transformer,
        device=device,
        text_col="text",
        topic_col="Global_Topic",
        keyword_col="Global_Topic_Keywords",
    )

    global_complete["Global_Topic_Quality"] = global_score

    validation_rows.append(
        {
            "Scope": "Global",
            "Category": "ALL",
            "Topic_Quality_Score": global_score,
            "Rows": len(global_complete),
            "Num_Topics": global_complete["Global_Topic"].nunique(),
        }
    )

    # Align and merge global topics into local dataset
    global_complete = global_complete.reset_index(drop=True)
    local_complete = local_complete.reset_index(drop=True)

    complete_df = pd.merge(
        local_complete,
        global_complete[
            [
                "ID",
                "Global_Topic",
                "Global_Topic_Keywords",
                "Global_Topic_Quality",
                "Cluster_Confidence",
                "Topic_Diversity",
            ]
        ].rename(
            columns={
                "Cluster_Confidence": "Global_Cluster_Confidence",
                "Topic_Diversity": "Global_Topic_Diversity",
            }
        ),
        on="ID",
        how="left",
    )
    validation_df = pd.DataFrame(validation_rows)

    return complete_df, validation_df


# ----------------------------
# MAIN PIPELINE EXECUTION
# ----------------------------
def run_pipeline(input_path: Path, output_dir: Path):
    if not input_path.exists():
        print(f"ERROR: Input dataset not found at: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Loading Checkpoint 1 dataset: {input_path}")
    df = pd.read_csv(input_path)
    required_cols = {"Text", "source", "category"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        print(f"ERROR: Input CSV is missing required columns: {missing_cols}", file=sys.stderr)
        sys.exit(1)

    print(f"      Loaded {len(df)} rows.")

    print("[2/4] Cleaning and preprocessing text...")
    df.drop_duplicates(inplace=True)
    df["Text"] = df["Text"].apply(clean)
    df.dropna(inplace=True)
    print(f"      Rows remaining after deduplication and cleaning: {len(df)}")

    if len(df) == 0:
        print("ERROR: No valid rows remain after data cleaning.", file=sys.stderr)
        sys.exit(1)

    # Device and models setup (Notebook Cell 7)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[3/4] Loading sentiment and irony models on device: {device}")
    if device == "cuda":
        torch.backends.cudnn.benchmark = True

    model_name_sent = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    encoder = AutoTokenizer.from_pretrained(model_name_sent)
    sentiment_model = AutoModelForSequenceClassification.from_pretrained(model_name_sent).to(device)
    sentiment_model.eval()

    model_name_irony = "cardiffnlp/twitter-roberta-base-irony"
    irony_tokenizer = AutoTokenizer.from_pretrained(model_name_irony)
    model_irony = AutoModelForSequenceClassification.from_pretrained(model_name_irony).to(device)
    model_irony.eval()

    irony_model = pipeline(
        "text-classification",
        model=model_irony,
        tokenizer=irony_tokenizer,
        device=0 if device == "cuda" else -1,
    )

    print("      Scoring sentiment and irony...")
    temp = get_sentiment_and_score(
        df["Text"].tolist(),
        df["source"].tolist(),
        df["category"].tolist(),
        encoder=encoder,
        sentiment_model=sentiment_model,
        irony_model=irony_model,
        device=device,
    )
    temp = pd.DataFrame(temp)

    # Free sentiment and irony models from GPU memory
    if device == "cuda":
        del sentiment_model, model_irony, encoder, irony_tokenizer, irony_model
        torch.cuda.empty_cache()

    df = df.reset_index(drop=True)
    temp = temp.reset_index(drop=True)
    df["ID"] = df.index
    temp["ID"] = temp.index

    new_data = pd.merge(df, temp, on="ID", how="inner")
    new_data.drop(columns=["Text_x"], inplace=True)
    new_data.rename(columns={"Text_y": "text"}, inplace=True)
    new_data["Sentiment"] = new_data["Sentiment"].astype(str).str.lower()

    checkpoint2_path = output_dir / "Checkpoint2.csv"
    new_data.to_csv(checkpoint2_path)
    print(f"      Saved Checkpoint 2 to: {checkpoint2_path}")

    # Preserve Unnamed: 0 column to match original notebook Checkpoint 3 schema
    if "Unnamed: 0" not in new_data.columns:
        new_data.insert(0, "Unnamed: 0", new_data.index)

    new_data = new_data.reset_index(drop=True)
    new_data["ID"] = new_data.index

    print("[4/4] Generating embeddings, UMAP reduction, HDBSCAN clustering, keywords, and quality metrics...")
    transformer = SentenceTransformer("all-roberta-large-v1", device="cpu")
    complete_dataset, validation_df = build_complete_dataset(new_data, transformer=transformer, device="cpu")

    complete_data_path = output_dir / "complete_data.csv"
    complete_dataset.to_csv(complete_data_path, index=False)
    print(f"      Saved Checkpoint 3 (complete_data.csv) to: {complete_data_path}")
    print("Pipeline finished at Checkpoint 3.")


def main():
    project_root = Path(__file__).resolve().parent.parent
    default_output = project_root / "output"

    parser = argparse.ArgumentParser(description="Run the extracted Sentiment Analysis ML Pipeline.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input CSV dataset (e.g., data/Checkpoint1.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help=f"Directory to save pipeline outputs (default: {default_output})",
    )

    args = parser.parse_args()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    run_pipeline(input_path, output_dir)


if __name__ == "__main__":
    main()
