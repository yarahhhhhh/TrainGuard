import os
import re
import json
from docling.document_converter import DocumentConverter
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()




###################################################################################################
# INCIDENT PROMPT
###################################################################################################
SYSTEM_PROMPT_INCIDENT = """
Classify incident text into standardized JSON. 
Incident types: COLLISION_HORS_PN, DERAILLEMENT, PASSAGE_A_NIVEAU,
ACCIDENT_PERSONNE_HORS_PN, INCIDENT_MATERIEL_ROULANT, AUTRE.
Impacts: COLLISION, DOMMAGE_INFRA, DOMMAGE_MATERIEL, DOMMAGE_HUMAIN,
RISQUE_SECONDAIRE, RETARD, ARRET.
Root causes and likelihood: INTEMPERIES, EROSION_SOL, DEFAILLANCE_TECHNIQUE,
ERREUR_HUMAINE, OBSTACLE_VOIE, INFRA_DEGRADEE, MAINTENANCE_INSUFFISANTE, VANDALISME.

If you identify a root cause, tag HIGH or LOW. 
If not present, omit the cause entirely.

Output JSON ONLY:
{
  "incident_type": "",
  "possible_impacts": [],
  "possible_root_causes": [["CAUSE", "LIKELIHOOD"]]
}
"""

###################################################################################################
# CAUSE PROMPT
###################################################################################################
SYSTEM_PROMPT_CAUSES = """
Tu dois extraire toutes les causes présentes dans le texte et les structurer pour Neo4J.

1. Identifier la cause racine parmi :
   INTEMPERIES, EROSION_SOL, DEFAILLANCE_TECHNIQUE,
   ERREUR_HUMAINE, OBSTACLE_VOIE, INFRA_DEGRADEE,
   MAINTENANCE_INSUFFISANTE, VANDALISME.

2. Classer chaque cause dans UNE catégorie normalisée parmi :
   DEFAILLANCE_COMPORTEMENTALE_HUMAINE
   NON_RESPECT_DES_REGLES
   OBSTACLE_SUR_VOIE
   INFRASTRUCTURE_INSUFFISANTE
   DEFAILLANCE_TECHNIQUE
   DEFAILLANCE_MAINTENANCE
   FACTEURS_METEO
   FACTEURS_GEOTECHNIQUES
   ACTE_MALVEILLANCE
   INATTENTION

3. Générer la commande Cypher :

MERGE (rc:RootCause {name:'<root_cause>'})
MERGE (cat:CategorieNormalisee {name:'<categorie_normalisee>'})
MERGE (cat)-[:EST_SOUS_CATEGORIE_DE]->(rc)

Si aucune cause n'est détectée → retourner []
Aucune sortie hors JSON.

Format OBLIGATOIRE :
[
  {
    "root_cause": "<cause racine>",
    "categorie_normalisee": "<categorie normalisée>",
    "cypher": "MERGE (...) MERGE (...) MERGE (...)"
  }
]
"""

###################################################################################################
# IMPACT PROMPT
###################################################################################################
SYSTEM_PROMPT_IMPACT = """
Identify impact categories and normalized sub-impact subtypes from the text.
No prose. JSON only.

Allowed impact categories:
COLLISION, DOMMAGE_INFRA, DOMMAGE_MATERIEL, DOMMAGE_HUMAIN,
RISQUE_SECONDAIRE, RETARD, ARRET.

Rules:
- Normalize sub-impacts (lowercase, underscores, minimal tokens).
- Assign each subtype to exactly one impact category.
- If no subtypes → return [].

Cypher generation:
MERGE (imp:Impact {name:'<impact_category>'})
MERGE (sub:SubImpact {name:'<normalized_subtype>'})
MERGE (sub)-[:EST_SOUS_IMPACT_DE]->(imp)

Output JSON ARRAY ONLY:
[
  {
    "impact_category": "<IMPACT>",
    "normalized_subtype": "<subtype>",
    "root_cause": "<ROOT_CAUSE or null>",
    "cypher_impact": "MERGE (...)"
  }
]
"""

###################################################################################################
# HELPERS
###################################################################################################
def extract_json_block(text: str):
    """Extract first valid JSON array or object from LLM output."""
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if not match:
        raise ValueError("Model output does not contain valid JSON.")
    return json.loads(match.group(1))

###################################################################################################
# DOCUMENT PROCESSING
###################################################################################################
def convert_doc(source_doc: str):
    output_doc = source_doc + ".md"
    converter = DocumentConverter()
    doc = converter.convert(source_doc).document
    md = doc.export_to_markdown()
    with open(output_doc, "w", encoding="utf-8") as f:
        f.write(md)

def load_md(path):
    with open(path, "r", encoding="utf8") as f:
        return f.read()


def chunk_by_title(md: str):
    pattern = re.compile(r'^(#{1,6})\s+(.+)', re.MULTILINE)
    matches = list(pattern.finditer(md))

    chunks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(md)
        chunks.append((m.group(2).strip(), md[start:end].strip()))
    return chunks

###################################################################################################
# CLASSIFIERS
###################################################################################################
def classify_incident_chunk(title, body):
    resp = client.responses.create(
        model="gpt-5",
        input=[{"role": "system", "content": SYSTEM_PROMPT_INCIDENT},
               {"role": "user", "content": body}]
    )
    data = extract_json_block(resp.output_text)
    return {"title": title, "analysis": data}


def classify_cause_chunk(title, body):
    resp = client.responses.create(
        model="gpt-5",
        input=[{"role": "system", "content": SYSTEM_PROMPT_CAUSES},
               {"role": "user", "content": body}]
    )
    data = extract_json_block(resp.output_text)
    return {"title": title, "analysis": data}


def classify_impact_chunk(title, body):
    resp = client.responses.create(
        model="gpt-5",
        input=[{"role": "system", "content": SYSTEM_PROMPT_IMPACT},
               {"role": "user", "content": body}]
    )
    data = extract_json_block(resp.output_text)
    return {"title": title, "analysis": data}

###################################################################################################
# BATCH PROCESSORS
###################################################################################################
def process_incident_chunks(chunks):
    return [classify_incident_chunk(t, b) for t, b in chunks]


def process_cause_chunks(chunks):
    return [classify_cause_chunk(t, b) for t, b in chunks]


def process_impact_chunks(chunks):
    return [classify_impact_chunk(t, b) for t, b in chunks]



