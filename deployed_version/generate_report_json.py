import json
import os
import uuid

def gen_id():
    return uuid.uuid4().hex[:20]

def make_card(x, y, w, h, title, measure_name, display_name):
    vid = gen_id()
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "cardVisual",
            "projections": {
                "Data": [{"queryRef": f"_Measures.{measure_name}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "m", "Entity": "_Measures", "Type": 0}],
                "Select": [{
                    "Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": measure_name},
                    "Name": f"_Measures.{measure_name}",
                    "NativeReferenceName": display_name
                }]
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_slicer(x, y, w, h, title, table_name, col_name):
    vid = gen_id()
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "slicer",
            "projections": {
                "Values": [{"queryRef": f"{table_name}.{col_name}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "s", "Entity": table_name, "Type": 0}],
                "Select": [{
                    "Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": col_name},
                    "Name": f"{table_name}.{col_name}",
                    "NativeReferenceName": col_name
                }]
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_bar_or_column(x, y, w, h, title, cat_table, cat_col, val_table, val_meas, legend_table=None, legend_col=None, is_stacked_100=False, is_bar=False):
    vid = gen_id()
    v_type = "hundredPercentStackedBarChart" if (is_stacked_100 and is_bar) else ("hundredPercentStackedColumnChart" if is_stacked_100 else ("clusteredBarChart" if is_bar else "clusteredColumnChart"))
    
    projections = {
        "Category": [{"queryRef": f"{cat_table}.{cat_col}"}],
        "Y": [{"queryRef": f"{val_table}.{val_meas}"}]
    }
    from_clause = [
        {"Name": "c", "Entity": cat_table, "Type": 0},
        {"Name": "m", "Entity": val_table, "Type": 0}
    ]
    select_clause = [
        {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": cat_col}, "Name": f"{cat_table}.{cat_col}", "NativeReferenceName": cat_col},
        {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": val_meas}, "Name": f"{val_table}.{val_meas}", "NativeReferenceName": val_meas}
    ]

    if legend_table and legend_col:
        projections["Series"] = [{"queryRef": f"{legend_table}.{legend_col}"}]
        from_clause.append({"Name": "l", "Entity": legend_table, "Type": 0})
        select_clause.append({"Column": {"Expression": {"SourceRef": {"Source": "l"}}, "Property": legend_col}, "Name": f"{legend_table}.{legend_col}", "NativeReferenceName": legend_col})

    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": v_type,
            "projections": projections,
            "prototypeQuery": {
                "Version": 2,
                "From": from_clause,
                "Select": select_clause
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_line_chart(x, y, w, h, title, cat_table, cat_col, val_table, val_meas, legend_table=None, legend_col=None):
    vid = gen_id()
    projections = {
        "Category": [{"queryRef": f"{cat_table}.{cat_col}"}],
        "Y": [{"queryRef": f"{val_table}.{val_meas}"}]
    }
    from_clause = [
        {"Name": "c", "Entity": cat_table, "Type": 0},
        {"Name": "m", "Entity": val_table, "Type": 0}
    ]
    select_clause = [
        {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": cat_col}, "Name": f"{cat_table}.{cat_col}", "NativeReferenceName": cat_col},
        {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": val_meas}, "Name": f"{val_table}.{val_meas}", "NativeReferenceName": val_meas}
    ]
    if legend_table and legend_col:
        projections["Series"] = [{"queryRef": f"{legend_table}.{legend_col}"}]
        from_clause.append({"Name": "l", "Entity": legend_table, "Type": 0})
        select_clause.append({"Column": {"Expression": {"SourceRef": {"Source": "l"}}, "Property": legend_col}, "Name": f"{legend_table}.{legend_col}", "NativeReferenceName": legend_col})

    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "lineChart",
            "projections": projections,
            "prototypeQuery": {
                "Version": 2,
                "From": from_clause,
                "Select": select_clause
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_donut_chart(x, y, w, h, title, cat_table, cat_col, val_table, val_meas):
    vid = gen_id()
    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "donutChart",
            "projections": {
                "Category": [{"queryRef": f"{cat_table}.{cat_col}"}],
                "Y": [{"queryRef": f"{val_table}.{val_meas}"}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [
                    {"Name": "c", "Entity": cat_table, "Type": 0},
                    {"Name": "m", "Entity": val_table, "Type": 0}
                ],
                "Select": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": cat_col}, "Name": f"{cat_table}.{cat_col}", "NativeReferenceName": cat_col},
                    {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": val_meas}, "Name": f"{val_table}.{val_meas}", "NativeReferenceName": val_meas}
                ]
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_scatter_chart(x, y, w, h, title, x_meas, y_meas, det_table, det_col, size_meas=None):
    vid = gen_id()
    projections = {
        "Category": [{"queryRef": f"{det_table}.{det_col}"}],
        "X": [{"queryRef": f"_Measures.{x_meas}"}],
        "Y": [{"queryRef": f"_Measures.{y_meas}"}]
    }
    from_clause = [
        {"Name": "d", "Entity": det_table, "Type": 0},
        {"Name": "m", "Entity": "_Measures", "Type": 0}
    ]
    select_clause = [
        {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": det_col}, "Name": f"{det_table}.{det_col}", "NativeReferenceName": det_col},
        {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": x_meas}, "Name": f"_Measures.{x_meas}", "NativeReferenceName": x_meas},
        {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": y_meas}, "Name": f"_Measures.{y_meas}", "NativeReferenceName": y_meas}
    ]
    if size_meas:
        projections["Size"] = [{"queryRef": f"_Measures.{size_meas}"}]
        select_clause.append({"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": size_meas}, "Name": f"_Measures.{size_meas}", "NativeReferenceName": size_meas})

    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "scatterChart",
            "projections": projections,
            "prototypeQuery": {
                "Version": 2,
                "From": from_clause,
                "Select": select_clause
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

def make_table_visual(x, y, w, h, title, items):
    vid = gen_id()
    projections = {"Values": []}
    from_dict = {}
    select_clause = []

    for item_type, ent, prop in items:
        qref = f"{ent}.{prop}"
        projections["Values"].append({"queryRef": qref})
        if ent not in from_dict:
            alias = f"e{len(from_dict)}"
            from_dict[ent] = alias
        alias = from_dict[ent]
        if item_type == "Column":
            select_clause.append({
                "Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop},
                "Name": qref,
                "NativeReferenceName": prop
            })
        else:
            select_clause.append({
                "Measure": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop},
                "Name": qref,
                "NativeReferenceName": prop
            })

    from_clause = [{"Name": alias, "Entity": ent, "Type": 0} for ent, alias in from_dict.items()]

    config = {
        "name": vid,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}}],
        "singleVisual": {
            "visualType": "tableEx",
            "projections": projections,
            "prototypeQuery": {
                "Version": 2,
                "From": from_clause,
                "Select": select_clause
            },
            "vcObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }
    return {
        "x": x, "y": y, "z": 0, "width": w, "height": h,
        "config": json.dumps(config),
        "filters": "[]",
        "query": "",
        "dataTransforms": ""
    }

# ----------------------------
# PAGE 1: Executive Overview & Brand Benchmarking
# ----------------------------
page1_visuals = [
    # KPI Cards
    make_card(10, 0, 240, 100, "Total Feedback Volume", "Total Feedback", "Total Feedback"),
    make_card(260, 0, 240, 100, "Average Rating", "Average Rating", "Average Rating"),
    make_card(510, 0, 240, 100, "Net Sentiment Score", "Net Sentiment Score", "Net Sentiment Score"),
    make_card(760, 0, 240, 100, "% Negative Feedback", "% Negative Feedback", "% Negative Feedback"),
    make_card(1010, 0, 250, 100, "% Positive Feedback", "% Positive Feedback", "% Positive Feedback"),
    
    # Slicers
    make_slicer(10, 110, 380, 80, "Date Range", "Dim_Date", "MonthYear"),
    make_slicer(400, 110, 420, 80, "Brand Slicer", "Dim_Brand", "BrandName"),
    make_slicer(830, 110, 430, 80, "Channel Slicer", "Dim_Channel", "ChannelName"),
    
    # Visuals
    make_bar_or_column(10, 200, 610, 250, "Brand Sentiment Comparison", "Dim_Brand", "BrandName", "_Measures", "Total Feedback", "Sheet1", "Sentiment", is_stacked_100=True, is_bar=True),
    make_line_chart(630, 200, 630, 250, "Net Sentiment Trend by Brand", "Dim_Date", "MonthYear", "_Measures", "Net Sentiment Score", "Dim_Brand", "BrandName"),
    make_bar_or_column(10, 460, 610, 250, "Average Customer Rating by Brand", "Dim_Brand", "BrandName", "_Measures", "Average Rating", is_bar=False),
    make_bar_or_column(630, 460, 630, 250, "Dominant Operational Issues (Top Negative Topics)", "Dim_Topic", "global_generalized_topic", "_Measures", "Negative Feedback Count", is_bar=True)
]

# ----------------------------
# PAGE 2: Channel & Competitive Voice of Customer
# ----------------------------
page2_visuals = [
    # KPI Cards
    make_card(10, 0, 300, 100, "Google Play Avg Rating", "Google Play Avg Rating", "Google Play Avg Rating"),
    make_card(320, 0, 300, 100, "Reddit Avg Rating", "Reddit Avg Rating", "Reddit Avg Rating"),
    make_card(630, 0, 300, 100, "YouTube Avg Rating", "YouTube Avg Rating", "YouTube Avg Rating"),
    make_card(940, 0, 320, 100, "Total Channel Feedback", "Total Feedback", "Total Feedback"),
    
    # Slicers
    make_slicer(10, 110, 400, 80, "Brand", "Dim_Brand", "BrandName"),
    make_slicer(420, 110, 420, 80, "Channel", "Dim_Channel", "ChannelName"),
    make_slicer(850, 110, 410, 80, "Sentiment", "Sheet1", "Sentiment"),
    
    # Visuals
    make_donut_chart(10, 200, 400, 250, "Channel Volume Distribution", "Dim_Channel", "ChannelName", "_Measures", "Total Feedback"),
    make_bar_or_column(420, 200, 430, 250, "Sentiment Share within Channel", "Dim_Channel", "ChannelName", "_Measures", "Total Feedback", "Sheet1", "Sentiment", is_stacked_100=True, is_bar=False),
    make_bar_or_column(860, 200, 400, 250, "Rating by Channel & Brand", "Dim_Channel", "ChannelName", "_Measures", "Average Rating", "Dim_Brand", "BrandName", is_bar=False),
    make_scatter_chart(10, 460, 610, 250, "Brand Positioning (Volume vs Net Sentiment)", "Total Feedback", "Net Sentiment Score", "Dim_Brand", "BrandName", "Negative Feedback Count"),
    make_line_chart(630, 460, 630, 250, "Weekly Sentiment Trajectory", "Dim_Date", "MonthYear", "_Measures", "Positive Feedback Count")
]

# ----------------------------
# PAGE 3: Topic Clustering Quality & Operational Diagnostics
# ----------------------------
page3_visuals = [
    # KPI Ribbon
    make_card(10, 0, 150, 90, "Global Topics", "Global Topic Count", "Global Topic Count"),
    make_card(170, 0, 150, 90, "Local Topics", "Local Topic Count", "Local Topic Count"),
    make_card(330, 0, 180, 90, "Global Coverage", "Global Assignment Coverage", "Global Assignment Coverage"),
    make_card(520, 0, 180, 90, "Local Coverage", "Local Assignment Coverage", "Local Assignment Coverage"),
    make_card(710, 0, 180, 90, "Global Noise %", "Global Unclustered Noise %", "Global Unclustered Noise %"),
    make_card(900, 0, 180, 90, "Global Confidence", "Global Cluster Confidence (Clustered)", "Global Confidence"),
    make_card(1090, 0, 170, 90, "Local Confidence", "Local Cluster Confidence (Clustered)", "Local Confidence"),
    
    # Slicers
    make_slicer(10, 100, 300, 70, "Brand", "Dim_Brand", "BrandName"),
    make_slicer(320, 100, 300, 70, "Channel", "Dim_Channel", "ChannelName"),
    make_slicer(630, 100, 350, 70, "Generalized Topic", "Dim_Topic", "global_generalized_topic"),
    make_slicer(990, 100, 270, 70, "Sentiment", "Sheet1", "Sentiment"),
    
    # Diagnostics Visuals
    make_bar_or_column(10, 180, 610, 260, "Topic Complaint Severity (Negative Volume)", "Dim_Topic", "global_topic_name", "_Measures", "Negative Feedback Count", is_bar=True),
    make_scatter_chart(630, 180, 630, 260, "Topic Impact vs Frequency Priority Matrix", "Total Feedback", "Average Rating", "Dim_Topic", "global_topic_name"),
    make_bar_or_column(10, 450, 480, 260, "Global vs Local Noise by Brand", "Dim_Brand", "BrandName", "_Measures", "Global Unclustered Count", is_bar=False),
    make_table_visual(500, 450, 760, 260, "Topic Coherence & Diagnostic Summary Table", [
        ("Column", "Dim_Topic", "Global_Topic"),
        ("Column", "Dim_Topic", "global_topic_name"),
        ("Column", "Dim_Topic", "global_generalized_topic"),
        ("Measure", "_Measures", "Total Feedback"),
        ("Measure", "_Measures", "Average Rating"),
        ("Measure", "_Measures", "% Negative Feedback")
    ])
]

# ----------------------------
# PAGE 4: Feedback Verbatim & Evidence Hub
# ----------------------------
page4_visuals = [
    # KPI Cards
    make_card(10, 0, 300, 90, "Filtered Records", "Total Feedback", "Total Feedback"),
    make_card(320, 0, 300, 90, "Average Rating", "Average Rating", "Average Rating"),
    make_card(630, 0, 300, 90, "Local Confidence", "Local Cluster Confidence (Clustered)", "Local Confidence"),
    make_card(940, 0, 320, 90, "Negative Count", "Negative Feedback Count", "Negative Feedback Count"),
    
    # Slicers
    make_slicer(10, 100, 240, 70, "Brand", "Dim_Brand", "BrandName"),
    make_slicer(260, 100, 240, 70, "Channel", "Dim_Channel", "ChannelName"),
    make_slicer(510, 100, 240, 70, "Sentiment", "Sheet1", "Sentiment"),
    make_slicer(760, 100, 300, 70, "Global Topic", "Dim_Topic", "global_generalized_topic"),
    make_slicer(1070, 100, 190, 70, "Date Range", "Dim_Date", "MonthYear"),
    
    # Master Table Visual
    make_table_visual(10, 180, 1250, 530, "Master Customer Feedback Evidence Table", [
        ("Column", "Sheet1", "Feedback_Date"),
        ("Column", "Dim_Brand", "BrandName"),
        ("Column", "Dim_Channel", "ChannelName"),
        ("Column", "Sheet1", "Sentiment"),
        ("Column", "Sheet1", "Rating"),
        ("Column", "Dim_Topic", "global_topic_name"),
        ("Column", "Sheet1", "text"),
        ("Column", "Sheet1", "url"),
        ("Column", "Sheet1", "Cluster_Confidence")
    ])
]

sections = [
    {"name": "Page1_ExecutiveOverview", "displayName": "Executive Overview & Benchmarking", "ordinal": 0, "width": 1280, "height": 720, "visualContainers": page1_visuals},
    {"name": "Page2_ChannelVoiceOfCustomer", "displayName": "Channel & Competitive VoC", "ordinal": 1, "width": 1280, "height": 720, "visualContainers": page2_visuals},
    {"name": "Page3_TopicQualityDiagnostics", "displayName": "Topic Diagnostics & NLP Quality", "ordinal": 2, "width": 1280, "height": 720, "visualContainers": page3_visuals},
    {"name": "Page4_FeedbackVerbatimHub", "displayName": "Feedback Verbatim & Evidence Hub", "ordinal": 3, "width": 1280, "height": 720, "visualContainers": page4_visuals}
]

report_layout = {
    "config": json.dumps({
        "version": "5.68",
        "themeCollection": {
            "baseTheme": {
                "name": "CY26SU04",
                "type": 2,
                "version": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"}
            }
        },
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "linguisticSchemaSyncVersion": 2,
        "settings": {
            "useNewFilterPaneExperience": True,
            "allowChangeFilterTypes": True,
            "useStylableVisualContainerHeader": True,
            "queryLimitOption": 6,
            "exportDataMode": 1,
            "useDefaultAggregateDisplayName": True,
            "useEnhancedTooltips": True
        }
    }),
    "layoutOptimization": 0,
    "sections": sections
}

base_dir = r"c:\Users\Prabhat\Desktop\Carear\projects\Sentiment Analysis System"
report_json_path = os.path.join(base_dir, "Customer_Sentiment_Intelligence.Report", "definition", "report.json")
with open(report_json_path, "w", encoding="utf-8") as f:
    json.dump(report_layout, f, indent=2)

print(f"Successfully generated 4-page report.json with {sum(len(s['visualContainers']) for s in sections)} visual containers across 4 sections!")
