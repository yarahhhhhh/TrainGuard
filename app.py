from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import os
import json
import tempfile
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))

app = FastAPI(title="SNCF Safety Pipeline API")

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


from pipeline import (
    convert_doc,
    load_md,
    chunk_by_title,
    process_incident_chunks,
    process_cause_chunks,
    process_impact_chunks,
)


# ---------------------------------------------------------
# 1) CONVERT PDF → MARKDOWN (input = path)
# ---------------------------------------------------------
@app.post("/convert_pdf")
def convert_pdf(pdf_path: str):
    if not os.path.isfile(pdf_path):
        return JSONResponse({"error": "PDF file not found"}, status_code=400)

    md_path = pdf_path + ".md"
    convert_doc(pdf_path)

    return {
        "status": "converted",
        "markdown_path": md_path
    }


@app.post("/process_incidents")
def process_incidents(md_path: str):
    if not os.path.isfile(md_path):
        return JSONResponse({"error": "Markdown file not found"}, status_code=400)

    md_text = load_md(md_path)
    chunks = chunk_by_title(md_text)

    incidents = process_incident_chunks(chunks)

    return {
        "status": "ok",
        "incidents": incidents
    }


@app.post("/process_causes")
def process_causes(md_path: str):
    if not os.path.isfile(md_path):
        return JSONResponse({"error": "Markdown file not found"}, status_code=400)

    md_text = load_md(md_path)
    chunks = chunk_by_title(md_text)

    causes = process_cause_chunks(chunks)

    return {
        "status": "ok",
        "causes": causes
    }


@app.post("/process_impacts")
def process_impacts(md_path: str):
    if not os.path.isfile(md_path):
        return JSONResponse({"error": "Markdown file not found"}, status_code=400)

    md_text = load_md(md_path)
    chunks = chunk_by_title(md_text)

    impacts = process_impact_chunks(chunks)

    return {
        "status": "ok",
        "impacts": impacts
    }


def split_merge_statements(cypher_string):
    """Split multiple MERGE statements into separate commands."""
    if not cypher_string:
        return []
    parts = cypher_string.split("MERGE ")
    return ["MERGE " + p.strip() for p in parts if p.strip()]


def ingest_all_into_neo4j(causes_json_path, incidents_json_path, impacts_json_path):

    causes_json = json.load(open(causes_json_path, 'r', encoding='utf-8'))
    incidents_json = json.load(open(incidents_json_path, 'r', encoding='utf-8'))
    impacts_json = json.load(open(impacts_json_path, 'r', encoding='utf-8'))

    cyphers = []

    # -------------------------
    # CAUSES
    # -------------------------
    for cause in causes_json:
        for entry in cause.get("analysis", []):
            cyphers.extend(split_merge_statements(entry.get("cypher", "")))

    # -------------------------
    # INCIDENTS
    # -------------------------
    for incident in incidents_json:
        for cy in incident.get("analysis", {}).get("cypher", []):
            cyphers.append(cy)

    # -------------------------
    # IMPACTS
    # -------------------------
    for impact_item in impacts_json:
        for entry in impact_item.get("analysis", []):
            if entry.get("cypher_impact"):
                cyphers.append(entry["cypher_impact"])

    # -------------------------
    # Push to Neo4J
    # -------------------------
    for c in cyphers:
        driver.execute_query(c)

    return {"status": "neo4j_ingested", "executed_cyphers": len(cyphers)}