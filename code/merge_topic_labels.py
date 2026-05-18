import pandas as pd


def _normalize_names_df(local_names, global_names):
    names_df = pd.DataFrame((local_names or []) + (global_names or [])).copy()
    if names_df.empty:
        return pd.DataFrame(columns=["topic_id", "scope", "category_name", "topic_name"])

    names_df["topic_id"] = pd.to_numeric(names_df.get("topic_id"), errors="coerce")
    names_df["scope"] = names_df.get("scope", "").astype(str).str.strip().str.lower()
    names_df["category_name"] = names_df.get("category_name", "").astype(str).str.strip().str.lower()
    names_df["topic_name"] = names_df.get("topic_name", "").astype(str).str.strip()

    names_df = names_df.dropna(subset=["topic_id"])
    names_df = names_df[names_df["topic_name"] != ""]
    names_df = names_df.drop_duplicates(subset=["scope", "category_name", "topic_id"], keep="first")
    return names_df


def _normalize_generalized_df(generalized_df):
    if generalized_df is None or len(generalized_df) == 0:
        return pd.DataFrame(columns=["category_name", "scope", "topic_name", "generalized_topic"])

    gen = generalized_df.copy()
    if "old" in gen.columns:
        gen = gen.rename(columns={"old": "topic_name"})
    if "new" in gen.columns:
        gen = gen.rename(columns={"new": "generalized_topic"})

    required_cols = ["category_name", "scope", "topic_name", "generalized_topic"]
    for col in required_cols:
        if col not in gen.columns:
            gen[col] = ""

    gen["scope"] = gen["scope"].astype(str).str.strip().str.lower()
    gen["category_name"] = gen["category_name"].astype(str).str.strip().str.lower()
    gen["topic_name"] = gen["topic_name"].astype(str).str.strip()
    gen["generalized_topic"] = gen["generalized_topic"].astype(str).str.strip()

    gen = gen[required_cols].drop_duplicates(subset=["category_name", "scope", "topic_name"], keep="first")
    return gen


def _build_complete_key_maps(complete_dataset):
    base = complete_dataset.copy()
    base["_cat_key"] = base["category"].astype(str).str.strip().str.lower()
    base["Local_Topic"] = pd.to_numeric(base["Local_Topic"], errors="coerce")
    base["Global_Topic"] = pd.to_numeric(base["Global_Topic"], errors="coerce")

    local_keys = (
        base[["_cat_key", "Local_Topic"]]
        .dropna(subset=["Local_Topic"])
        .drop_duplicates()
        .rename(columns={"_cat_key": "category_name", "Local_Topic": "topic_id"})
    )

    global_keys = (
        base[["Global_Topic"]]
        .dropna(subset=["Global_Topic"])
        .drop_duplicates()
        .rename(columns={"Global_Topic": "topic_id"})
    )
    return base, local_keys, global_keys


def merge_topic_labels(complete_dataset, local_names, global_names, generalized_df):
    names_df = _normalize_names_df(local_names, global_names)
    gen = _normalize_generalized_df(generalized_df)

    names_with_gen = names_df.merge(
        gen[["category_name", "scope", "topic_name", "generalized_topic"]],
        on=["category_name", "scope", "topic_name"],
        how="left",
    )
    names_with_gen["generalized_topic"] = names_with_gen["generalized_topic"].fillna(names_with_gen["topic_name"])

    local_named = (
        names_with_gen[names_with_gen["scope"] == "local"][["category_name", "topic_id", "topic_name", "generalized_topic"]]
        .rename(columns={"topic_name": "local_topic_name", "generalized_topic": "local_generalized_topic"})
        .drop_duplicates(subset=["category_name", "topic_id"], keep="first")
    )
    global_named = (
        names_with_gen[names_with_gen["scope"] == "global"][["topic_id", "topic_name", "generalized_topic"]]
        .rename(columns={"topic_name": "global_topic_name", "generalized_topic": "global_generalized_topic"})
        .drop_duplicates(subset=["topic_id"], keep="first")
    )

    merged, local_keys, global_keys = _build_complete_key_maps(complete_dataset)

    # Build maps from dataset keys first, then attach labels.
    local_map = local_keys.merge(local_named, on=["category_name", "topic_id"], how="left")
    global_map = global_keys.merge(global_named, on=["topic_id"], how="left")

    # Deterministic fallback labels for any missing name/generalization.
    local_map["local_topic_name"] = local_map["local_topic_name"].fillna(
        local_map["category_name"].str.title() + " Topic " + local_map["topic_id"].astype("Int64").astype(str)
    )
    local_map["local_generalized_topic"] = local_map["local_generalized_topic"].fillna(local_map["local_topic_name"])

    global_map["global_topic_name"] = global_map["global_topic_name"].fillna(
        "Global Topic " + global_map["topic_id"].astype("Int64").astype(str)
    )
    global_map["global_generalized_topic"] = global_map["global_generalized_topic"].fillna(global_map["global_topic_name"])

    merged = merged.merge(
        local_map,
        left_on=["_cat_key", "Local_Topic"],
        right_on=["category_name", "topic_id"],
        how="left",
        validate="many_to_one",
    ).drop(columns=["category_name", "topic_id"], errors="ignore")

    merged = merged.merge(
        global_map,
        left_on="Global_Topic",
        right_on="topic_id",
        how="left",
        validate="many_to_one",
    ).drop(columns=["topic_id"], errors="ignore")

    merged = merged.drop(columns=["_cat_key"], errors="ignore")

    merged.loc[merged["Local_Topic"] == -1, "local_topic_name"] = "Noise / Unclustered"
    merged.loc[merged["Local_Topic"] == -1, "local_generalized_topic"] = "Noise / Unclustered"
    merged.loc[merged["Global_Topic"] == -1, "global_topic_name"] = "Noise / Unclustered"
    merged.loc[merged["Global_Topic"] == -1, "global_generalized_topic"] = "Noise / Unclustered"

    diagnostics = {
        "missing_local_mapping_before_fallback": int(local_map["local_topic_name"].isna().sum()),
        "missing_global_mapping_before_fallback": int(global_map["global_topic_name"].isna().sum()),
        "dataset_local_keys": int(len(local_keys)),
        "dataset_global_keys": int(len(global_keys)),
        "named_local_keys": int(len(local_named)),
        "named_global_keys": int(len(global_named)),
    }

    return merged, local_map, global_map, diagnostics
