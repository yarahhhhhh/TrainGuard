# SNCF Safety Knowledge Extraction Pipeline

This project extracts **structured railway safety knowledge** from unstructured incident documents and prepares it for ingestion into a **Neo4J graph-based safety system**.  
Its purpose is to help railway safety personnel analyze incidents, identify root causes, and justify maintenance or budget decisions using a connected safety knowledge graph.

---

## Overview

### 1. PDF → Markdown
Documents are converted to markdown using **Docling**. This provides a uniform text format for analysis.

### 2. Markdown Chunking
The markdown document is segmented into sections based on titles (`#`, `##`, etc.).  
Each chunk is processed independently.

### 3. Three Classification Modules

#### A. Incident Classification
Outputs:
- `incident_type`
- `possible_impacts`
- `possible_root_causes` (with HIGH/LOW likelihood)
- Cypher defining:
  - Incident → Impact  
  - Incident → RootCause  
  - Impact → RootCause  

#### B. Cause Classification
Outputs:
- root cause (chosen from a fixed taxonomy)
- normalized causal category
- Cypher linking:
  - Category → RootCause

#### C. Impact Classification
Outputs:
- impact category
- normalized sub-impact subtype
- optional inferred root cause
- Cypher linking:
  - SubImpact → Impact

### 4. JSON Outputs
Each classifier produces a JSON file:

├── incidents.json
├── causes.json
└── impacts.json

yaml
Copier le code

All files are ready for Neo4J ingestion.

---

## FastAPI Endpoints

### Convert PDF to Markdown
POST /convert_pdf?pdf_path=path/to/file.pdf

### Process Incidents
POST /process_incidents?md_path=path/to/file.md

### Process Causes
POST /process_causes?md_path=path/to/file.md

### Process Impacts
POST /process_impacts?md_path=path/to/file.md

## Neo4J Integration

The pipeline produces structured JSON files (`incidents.json`, `causes.json`, `impacts.json`) that already contain **fully generated Cypher statements**.  
These Cypher statements express all required graph relationships for a safety-knowledge model.

### What Gets Written to Neo4J

The system generates and ingests four major types of nodes:

- **IncidentType**
- **Impact**
- **SubImpact**
- **RootCause**
- **CategorieNormalisee**

And several relationship types:

- `(:IncidentType)-[:HAS_IMPACT]->(:Impact)`
- `(:IncidentType)-[:HAS_CAUSE {likelihood}]->(:RootCause)`
- `(:Impact)-[:LINKED_TO_CAUSE]->(:RootCause)`
- `(:SubImpact)-[:EST_SOUS_IMPACT_DE]->(:Impact)`
- `(:CategorieNormalisee)-[:EST_SOUS_CATEGORIE_DE]->(:RootCause)`

These relations form a **multi-layered safety graph** connecting:

**Incident → Impact → Root Cause → Normalized Category**

This creates a navigable structure where analysts can:

- explore causal chains  
- compare incident families  
- trace common failure patterns  
- justify maintenance decisions  
- support risk scoring and prioritization  

### How Ingestion Works

The ingestion route (`/neo4j_ingest`) reads the three JSON files and extracts every Cypher statement.  
Each statement is executed sequentially using:

```python
driver.execute_query(cypher)
